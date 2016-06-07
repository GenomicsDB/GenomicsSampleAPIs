import time, uuid
from time import strftime
from sqlalchemy import create_engine, and_, or_, exc
from sqlalchemy.orm import sessionmaker
from metadb.models import bind_engine, Individual, Sample, CallSet, DBArray, ReferenceSet, Reference, Workspace, VariantSet, CallSetToDBArrayAssociation
from collections import OrderedDict, namedtuple

class DBImport():
  """
  Keeps the enging and the session maker for the database
  """
  def __init__(self, database, echo_debug=False):
    self.engine = create_engine(database, echo=echo_debug)
    self.Session = sessionmaker(bind = self.engine, expire_on_commit=False)

  def getSession(self):
    """
    Returns the Query object that can be used with "with" clause
    """
    return Import(self)


class Import():
  """
  Manages the session for importing
  This will be the class that verifies registration and imports data into metadb
  """

  def __init__(self, db):
    self.db = db

  def __enter__(self):
    self.session = self.db.Session()
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.session.close()


  def registerReferenceSet(self, guid, assembly_id, source_accessions=None, description=None, references=None):
    """
    ReferenceSet registration occurs from a assembly config file. See hg19.json for example.
    Requires assembly ids and guids to be unique.
    """

    thisReferenceSet = self.session.query(ReferenceSet).filter(or_(ReferenceSet.assembly_id==assembly_id, ReferenceSet.guid==guid)).first()

    if thisReferenceSet is None:

      try:
        thisReferenceSet = ReferenceSet(guid=guid, assembly_id=assembly_id, description=description)
        self.session.add(thisReferenceSet)
        self.session.commit()

      except exc.DataError as e:
        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

      if references:
        # use pyvcf like ordered dict to avoiding having to specify reference order manually
        refs = sortReferences(references)
        for ref in refs:
          self.registerReference(str(uuid.uuid4()), thisReferenceSet.id, ref, refs[ref].length)

    return thisReferenceSet


  def registerReference(self, guid, reference_set_id, name, length):
    """
    Registers a Reference. Most often called by registerReferenceSet.
    Requires a Reference name be unique for all references in a reference set
    """
    # contig MT is same as contig M, in meta db we will always use M to be consistent
    if name == 'MT' :
      name = 'M'

    thisReference = self.session.query(Reference).filter(and_(Reference.reference_set_id==reference_set_id, Reference.name==name)).first()
    
    if thisReference is None:
      try:
        thisReference = Reference(name=name, reference_set_id=reference_set_id, length=length, guid=guid)
        self.session.add(thisReference)
        self.session.commit()

      except exc.DataError as e:
        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

    return thisReference


  def registerWorkspace(self, guid, name):
    """
    Registers a workspace. 
    Workspace name is the path to the workspace directory. This is assumed unique per metadb instance.
    """

    # if the name ends with a / then remove it from the name.
    # This is done only for consistency in workspace name 
    # since users could have / or not for the workspace.
    name = name.rstrip('/')

    thisWorkspace = self.session.query(Workspace).filter(and_(Workspace.name==name)).first()

    if thisWorkspace is None:
      try:
        thisWorkspace = Workspace(guid=guid, name=name)
        self.session.add(thisWorkspace)
        self.session.commit()

      except exc.DataError as e:
        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

    return thisWorkspace


  def registerDBArray(self, guid, reference_set_id, workspace_id, name):
    """
    Registers a DBArray.
    An array is unique named folder in a unique workspace path and a given reference id.
    """

    # array is a unique set of workspace, array, and reference set association
    thisDBArray = self.session.query(DBArray)\
                       .filter(and_(DBArray.reference_set_id==reference_set_id, DBArray.workspace_id==workspace_id, DBArray.name==name))\
                       .first()

    if thisDBArray is None:
      try:
        thisDBArray = DBArray(guid=guid, reference_set_id=reference_set_id, workspace_id=workspace_id, name=name)
        self.session.add(thisDBArray)
        self.session.commit()

      except exc.DataError as e:

        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

    return thisDBArray


  def registerVariantSet(self, guid, reference_set_id, dataset_id=None, metadata=None):
    """
    Register variant set.
    """

    thisReferenceSet = self.session.query(ReferenceSet)\
                           .filter(ReferenceSet.id==reference_set_id).first()

    if thisReferenceSet is None:
      raise ValueError("ReferenceSet must be registered before registering this VariantSet : {0} ".format(reference_set_id))

    thisVariantSet = self.session.query(VariantSet).filter(VariantSet.guid==guid).first()

    if thisVariantSet is None:
      try:
        thisVariantSet = VariantSet(
            guid=guid,
            reference_set_id=reference_set_id,
            dataset_id=dataset_id,
            variant_set_metadata=metadata
          )
        self.session.add(thisVariantSet)
        self.session.commit()

      except exc.DataError as e:
        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

    return thisVariantSet


  def updateVariantSetList(self, variant_set_ids, callset=None):
    """
    Add a VariantSet to a callset variantset list.
    Duplicate variant sets cannot be added to a callset variant set list
    ie. set(callset.variant_sets)
    """

    thisVariantSets = self.session.query(VariantSet).filter(VariantSet.id.in_(variant_set_ids)).all()
    
    if len(thisVariantSets) != len(variant_set_ids):
      raise ValueError("VariantSet must be registered before being added to CallSet VariantSet list.")

    if callset is None:
      return thisVariantSets

    callset.variant_sets.extend(x for x in thisVariantSets if x not in callset.variant_sets)

    return callset

  def addCallSetToDBArrayAssociation(self, callset_id, db_array_id):
    """
    Register a callset to an array. 
    All callsets in an array must be unique, but a callset can belong to multiple arrays.
    """

    # check if callset is registered to array already
    thisCallSetToDBArrayAssociation = self.session.query(CallSetToDBArrayAssociation)\
                           .filter(and_(CallSetToDBArrayAssociation.db_array_id==db_array_id, CallSetToDBArrayAssociation.callset_id==callset_id))\
                           .first()
    
    if thisCallSetToDBArrayAssociation is None:

      thisCallSetToDBArrayAssociation = CallSetToDBArrayAssociation(db_array_id=db_array_id, callset_id=callset_id)
      self.session.add(thisCallSetToDBArrayAssociation)
      self.session.commit()


  def registerCallSet(self, guid, source_sample_guid, target_sample_guid, workspace, array_name, variant_set_ids=None, info=None, name=None):
    """
    Register a callset.
    Associate a new or already existing callset to a variant set.
    Register an already existing callset to an already existing array.
    Registration requires a unique guid or a unique (name, source_sample, target_sample).
    """

    # if the name ends with a / then remove it from the name.
    # This is done only for consistency in workspace name 
    # since users could have / or not for the workspace.
    workspace = workspace.rstrip('/')

    # get samples
    thisSourceSample = self.session.query(Sample.id).filter(Sample.guid==source_sample_guid).first()
    thisTargetSample = self.session.query(Sample.id).filter(Sample.guid==target_sample_guid).first()

    if thisSourceSample is None or thisTargetSample is None:
      raise ValueError("Issue retrieving Sample info, check: source sample {0}, or target sample {1}".format(source_sample_guid, target_sample_guid))

    # get array
    thisDBArray = self.session.query(DBArray)\
                    .join(Workspace)\
                    .filter(Workspace.name == workspace)\
                    .filter(DBArray.name == array_name)\
                    .first()

    if thisDBArray is None:
      raise ValueError("DBArray needs to exist for CallSet Registration : {0} ".format(array_name))

    thisCallSet = self.session.query(CallSet)\
                  .filter(or_(CallSet.guid==guid, \
                         and_(CallSet.name==name, \
                            CallSet.source_sample_id==thisSourceSample[0], \
                            CallSet.target_sample_id==thisTargetSample[0]))).first()

    if thisCallSet is None:
      if variant_set_ids is None:
        raise ValueError("Registration of a CallSet requires association to an existing VariantSet.")

      try:
        thisCallSet = CallSet(guid=guid, 
          name=name, 
          created=int(time.time()*1000), 
          updated=int(time.time()*1000),
          info=info,
          source_sample_id=thisSourceSample[0],
          target_sample_id=thisTargetSample[0],
          variant_sets=self.updateVariantSetList(variant_set_ids)
          )

        self.session.add(thisCallSet)
        self.session.commit()

      except exc.DataError as e:
        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

    elif variant_set_ids:
      # avoid calling and registering again if this is a repeat variant set id
      vs = set(variant_set_ids).difference([x.id for x in thisCallSet.variant_sets])
      if len(vs) > 0:
        self.updateVariantSetList(vs, callset=thisCallSet)
        self.session.add(thisCallSet)
        self.session.commit()
    
    # adding this callset to the dbarray, performs check if already registered to array
    self.addCallSetToDBArrayAssociation(db_array_id=thisDBArray.id, callset_id=thisCallSet.id)

    return thisCallSet


  def registerSample(self, guid, individual_guid, name=None, info=None):
    """
    Registration of a Sample requires an individual be registered.
    Unique guid, or unique name per individual
    ie. an individual cannot have two samples with the same name
    """

    thisIndividual = self.session.query(Individual).filter(Individual.guid==individual_guid).first()

    if thisIndividual is None:
      raise ValueError("Invalid Individual Id : {0} ".format(individual_guid))

    thisSample = self.session.query(Sample).filter(or_(Sample.guid==guid, and_(Sample.name==name, Sample.individual_id==thisIndividual.id))).first()


    if thisSample is None:
      try:
        thisSample = Sample(guid=guid, individual_id=thisIndividual.id, name=name, info=info)
        self.session.add(thisSample)
        self.session.commit()

      except exc.DataError as e:

        self.session.rollback()
        raise ValueError("{0} : {1} ".format(str(e), guid))

    return thisSample


  def registerIndividual(self, guid, name, info=None):
    """ 
    Registration of an individual requires a guid and a name.
    Name can be None to support retrival from registerSample
    """
    individual = self.session.query(Individual)\
               .filter(or_(Individual.guid==guid, Individual.name==name)).first()

    if individual is None:

      try:
        individual = Individual(name=name,
          guid=guid,
          info=info,
          record_update_time=strftime("%Y-%m-%d %H:%M:%S%S.%S%S%S"),
          record_create_time=strftime("%Y-%m-%d %H:%M:%S%S.%S%S%S"))
        self.session.add(individual)
        self.session.commit()

      except (exc.DataError, exc.IntegrityError) as e:
        
        self.session.rollback()
        raise ValueError("{0} : {1} : {2} ".format(str(e), guid, name))

    return individual

def sortReferences(references):
  """
  Used in registerReferenceSet to sort and represent a list of references like pyvcf.
  This removes the need user specified reference list order.
  """
  # sorting and represent a list of references like pyvcf
  Contig = namedtuple('Contig', 'id length')

  if references.__class__ != OrderedDict().__class__:
    vcflike_refs = {str(key):Contig(id=str(key), length=value) for (key, value) in references.items()}
    references = OrderedDict(sorted(vcflike_refs.items(), key=lambda (key, value): int(key) if key.isdigit() else key))

  if 'MT' in references:
    references['M'] = references.pop('MT')
    references['M'] = Contig(id='M', length=references['M'].length)

  return references

