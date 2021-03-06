"""
  The MIT License (MIT)
  Copyright (c) 2016 Intel Corporation

  Permission is hereby granted, free of charge, to any person obtaining a copy of 
  this software and associated documentation files (the "Software"), to deal in 
  the Software without restriction, including without limitation the rights to 
  use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of 
  the Software, and to permit persons to whom the Software is furnished to do so, 
  subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all 
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS 
  FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR 
  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
  IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN 
  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from itertools import chain

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from itertools import chain

from metadb.models import Field
from metadb.models import Individual
from metadb.models import Workspace
from metadb.models import DBArray
from metadb.models import CallSetToDBArrayAssociation
from metadb.models import Reference
from metadb.models import ReferenceSet
from metadb.models import CallSet
from metadb.models import VariantSet
from metadb.models import CallSetVariantSet
from metadb.models import Sample

class DBQuery():
    """ keeps the engine and the session maker for the database """

    def __init__(self, database):
        self.engine = create_engine(database)
        self.Session = sessionmaker(bind = self.engine)

        # Pre-fetch field mapping since the table is usually small and can be
        # looked up in memory quickly
        with self.getSession() as s:
            fields = s.session.query(Field)
        self.fieldNameDict = dict()
        for item in fields:
            self.fieldNameDict[item.id] = item.field

    def getSession(self):
        """
        Returns the Query object that can be used with "with" clause
        """
        return Query(self)


class Query():
    """
    Manages the session for queries
    """

    def __init__(self, db):
        self.db = db
        # cache for translating tile to contig quickly
        self.array_id = None
        self.contig = None
        self.offset = None
        self.length = None

    def __enter__(self):
        self.session = self.db.Session()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def individualId2Name(self, idx):
        """
        Takes a single index or a list of indices, and returns
        a list of sample names.
        If the id is invalid, the value corresponding to that index
        will be None
        """
        if not isinstance(idx, list):
            idx = [idx]

        resultTuple = self.session.query(
            Individual.id, 
            Individual.name)\
            .filter(Individual.id.in_(idx))\
            .all()
        resultDict = dict(resultTuple)
        del resultTuple
        return fillResults(idx, resultDict)

    def individualName2Id(self, name):
        """
        Takes a single name or a list of names, and returns
        a list of ids.
        If the name is invalid, the value corresponding to that index
        will be None
        """
        if not isinstance(name, list):
            name = [name]

        resultTuple = self.session.query(
            Individual.name,
            Individual.id)\
            .filter(Individual.name.in_(name))\
            .all()
        resultDict = dict(resultTuple)
        del resultTuple
        return fillResults(name, resultDict)

    def arrayId2TileNames(self, array_idx):
        """
        Given a array idx, returns a tuple of workspace and array name
        """
        result = self.session.query(
            Workspace.name,
            DBArray.name)\
            .filter(DBArray.id == array_idx)\
            .all()
        if len(result) != 1:
            raise ValueError("Invalid Array Id : {0} ".format(array_idx))
        return result[0]

    def tileNames2ArrayIdx(self, workspace, arrayName):
        """
        Given a workspace and array name, returns the array_idx
        """
        # if the name ends with a / then remove it from the name.
        # This is done only for consistency in workspace name
        # since users could have / or not for the workspace.
        workspace = workspace.rstrip('/')

        result = self.session.query(
            DBArray.id)\
            .join(Workspace)\
            .filter(DBArray.name == arrayName)\
            .filter(Workspace.name == workspace)\
            .all()

        if len(result) != 1:
            raise ValueError(
                "Invalid workspace: {0} or array name: {1}".format(
                    workspace, arrayName))
        return result[0][0]

    def arrayId2TileRows(self, array_idx):
        """
        Given a array_idx return a list of tile row ids that are valid
        """
        result = self.session.query(
            CallSetToDBArrayAssociation.tile_row_id)\
            .filter(CallSetToDBArrayAssociation.db_array_id == array_idx)\
            .all()
        return toList(result)

    def fieldId2Name(self, fieldID):
        return self.db.fieldNameDict[fieldID]

    def contig2Tile(self, array_idx, contig, positionList):
        """
        Given a contig and list of positions for an array, returns the list of tile
        column positions
        If the input positionList is a single element, then the returned list has 1 element
        """
        # contig MT is same as contig M, in meta db we will always use M to be
        # consistent
        if contig == 'MT':
            contig = 'M'
        if not isinstance(positionList, list):
            positionList = [positionList]
        if not (self.contig and self.contig == contig and self.array_id == array_idx): 
            result = self.session.query(
                Reference.tiledb_column_offset,
                Reference.length)\
                .join(ReferenceSet, DBArray)\
                .filter(DBArray.id == array_idx)\
                .filter(Reference.name == contig)\
                .all()
    
            if len(result) != 1:
                raise ValueError(
                    "Invalid array id: {0} or contig: {1}".format(
                        array_idx, contig))
            
            self.array_id = array_idx
            self.contig = contig
            self.offset = result[0][0]
            self.length = result[0][1]

        count = len(positionList)

        resultList = [None] * count

        for i in xrange(0, count):
            if positionList[i] > self.length:
                raise ValueError(
                    "Invalid Query. Position {0} is > length of contig: {1} ".format(
                        positionList[i], self.length))
            elif positionList[i] < 0:
                raise ValueError(
                    "Invalid Query. Position {0} should be positive ".format(
                        positionList[i]))
            # Contig, position is 1-based (in other words VCF is 1-based) and
            # tile db is 0 based so subtract 1
            resultList[i] = self.offset + positionList[i] - 1

        return resultList

    def tile2Contig(self, array_idx, positionList):
        if not isinstance(positionList, list):
            positionList = [positionList]
        count = len(positionList)
        resultContigList = [None] * count
        resultPositionList = [None] * count

        for i in xrange(0, count):
            # Check if we can optimize the translation without going to the DB
            if self.offset is not None and positionList[i] >= self.offset and (
                    positionList[i] - self.offset) <= self.length and self.array_id == array_idx:
                # Since the all positions in the input list is greater than or equal to offset and
                # less than or equal to the lenth of the contig, use the current result from the DB to
                # translate all the positions
                resultContigList[i] = self.contig
                # Contig, position is 1-based (in other words VCF is 1-based)
                # and tile db is 0 based so add 1
                resultPositionList[i] = positionList[i] - self.offset + 1
                continue
            # Get the info from DB since the cache is not available or
            # the cached values are not relevant to the current request
            result = self.session.query(
                Reference.name,
                Reference.tiledb_column_offset,
                Reference.length)\
                .join(ReferenceSet, DBArray)\
                .filter(DBArray.id == array_idx)\
                .filter(Reference.tiledb_column_offset <= positionList[i])\
                .order_by(Reference.tiledb_column_offset.desc())\
                .first()
            if result is None or len(result) != 3:
                raise ValueError(
                    "Invalid Position {0} for array id {1}".format(
                        positionList[i], array_idx))
            # Update cache
            self.array_id = array_idx
            self.contig = result[0]
            self.offset = result[1]
            self.length = result[2]
            resultContigList[i] = self.contig
            # Contig, position is 1-based (in other words VCF is 1-based) and
            # tile db is 0 based so add 1
            resultPositionList[i] = positionList[i] - self.offset + 1
            if resultPositionList[i] > self.length:
                raise ValueError(
                    "Invalid Position {0} > total length for array id {1}".format(
                        positionList[i], array_idx))
        return resultContigList, resultPositionList

    def getArrayRows(self, array_idx = None, variantSets = [], callSets = []):
        """
        The method returns a dictionary whose key is the array_idx and the value is a list of tile_row_id.
        Each of the parameter is a filter that is applied, and all parameters are optional.
        Both variantSets and callsets list takes guid.
        """
        queryStatement = self.session.query(
            CallSetToDBArrayAssociation.db_array_id,
            CallSetToDBArrayAssociation.tile_row_id)
        if array_idx:
            queryStatement = queryStatement.filter(
                CallSetToDBArrayAssociation.db_array_id == array_idx)
        if callSets and len(callSets):
            queryStatement = queryStatement.join(
                CallSet)\
                .filter(CallSet.guid.in_(callSets))
        if variantSets and len(variantSets):
            if not (callSets and len(callSets)):
                queryStatement = queryStatement.join(CallSet)
            queryStatement = queryStatement.join(
                CallSetVariantSet)\
                .join(VariantSet)\
                .filter(VariantSet.guid.in_(variantSets))

        resultDict = Dictlist()
        for k, v in queryStatement.all():
            resultDict[k] = v
        return resultDict

    def tileRow2CallSet(self, array_idx, tile_row_id):
        """
        Given a array id and tile rows, returns a list of tuples of the form
        (tile_row_id, call set id, call set guid, call set name)
        """
        if( isinstance(tile_row_id, list) != True ):
            tile_row_id = [tile_row_id]
        result = self.session.query(
            CallSetToDBArrayAssociation.tile_row_id,
            CallSet.id,
            CallSet.guid,
            CallSet.name).join(
            CallSet, CallSetToDBArrayAssociation.callset_id == CallSet.id)\
            .filter(CallSetToDBArrayAssociation.tile_row_id.in_(tile_row_id))\
            .filter(
            CallSetToDBArrayAssociation.db_array_id == array_idx).all()

        if len(result) < 1:
            raise ValueError(
                "Invalid Array Id: {0} and/or tile row id: {1}".format(array_idx, tile_row_id))
        return result

    def datasetId2VariantSets(self, datasetId):
        """
        Given a dataset id return variant_set objects
        """
        result = self.session.query(VariantSet)\
            .filter(VariantSet.dataset_id == datasetId)\
            .all()

        return result

    def referenceSetIdx2ReferenceSetGUID(self, referenceSetIdx):
        """
        Given a reference set idx return a reference set GUID
        """
        result = self.session.query(
            ReferenceSet.guid)\
            .filter(ReferenceSet.id == referenceSetIdx)\
            .all()

        if len(result) != 1:
            raise ValueError(
                "Invalid Reference Set Idx: {0}".format(referenceSetIdx))
        return result[0][0]

    def callSetId2VariantSet(self, callSetId):
        """
        Given a call set id, returns a tuple of
        (variant set idx, variant set guid)
        """
        # TODO ommitting this function since variant set is not being used
        result = self.session.query(
            VariantSet.id,
            VariantSet.guid)\
            .join(CallSetVariantSet)\
            .filter(CallSetVariantSet.callset_id == callSetId)\
            .all()

        if len(result) != 1:
            raise ValueError("Invalid call set Id: {0}".format(callSetId))
        return result[0]

    def callSetIds2TileRowId(
            self, callSetIds, workspace, arrayName, isGUID = True):
        """
        Given a list of call set ids (guids), workspace, and arrayName
        returns the tile row ids that are valid
        This is required for callset filtering.
        """
        # if the name ends with a / then remove it from the name.
        # This is done only for consistency in workspace name
        # since users could have / or not for the workspace.
        workspace = workspace.rstrip('/')

        queryStatement = self.session.query(
            CallSetToDBArrayAssociation.tile_row_id)\
            .join(DBArray)\
            .join(Workspace)\
            .join(CallSet)\
            .filter(DBArray.name == arrayName)\
            .filter(Workspace.name == workspace)
        if isGUID:
            queryStatement = queryStatement.filter(
                CallSet.guid.in_(callSetIds))
        else:
            queryStatement = queryStatement.filter(
                CallSet.id.in_(callSetIds))
        result = queryStatement.all()

        return [str(i) for i in list(chain.from_iterable(result))]

    def variantSetGUID2Id(self, variantSetGUID):
        """
        Given a variant set guid, returns a variant set idx
        This is required to support new SearchVariantsRequest schema
        """
        result = self.session.query(
            VariantSet)\
            .filter(VariantSet.guid == variantSetGUID)\
            .all()
        if len(result) != 1:
            # raise ValueError("Invalid variant set Id: {0}".format(variantSetId))
            # if no variantSetId specified, then just pick the first one - this
            # is to get around new ga4gh api changes / cf ga4gh service
            # conflicts
            result = self.session.query(VariantSet)\
                .all()
        return (result[0].id, result[0].guid)

    def arrayIdx2CallSets(self, array_idx):
        """
        Returns a tuple of (callset, sourceSampleId, targetSampleId) from callsets belonging to a single array..
        Example: [(f408d471-fe65-4a13-8ea6-cdd75adf6214, SourceSampleId, TargetSampleId)]
        """
        result = self.session.query(
            CallSet.guid,
            CallSet.source_sample_id,
            CallSet.target_sample_id)\
            .join(CallSetToDBArrayAssociation)\
            .filter(CallSetToDBArrayAssociation.db_array_id == array_idx)\
            .all()

        if len(result) == 0:
            raise ValueError("Invalid array idx: {0}".format(array_idx))

        return result

    def sampleIdx2SampleName(self, sample_idx):
        """
        Given a sampleId, return the sampleName
        """
        result = self.session.query(Sample)\
                     .filter(Sample.id == sample_idx)\
                     .all()

        if len(result) != 1:
            raise ValueError("Invalid sample idx: {0}".format(sample_idx))

        return result[0].name

####### Helper Functions #######


def fillResults(sourceList, mapper):
    """
    picks values in the sourceList as keys and gets the values from
    mapper which is a dictionary
    """
    result = [None] * len(sourceList)
    index = 0
    for v in sourceList:
        try:
            result[index] = mapper[v]
        except Exception as e:
            # If we have an exception then value v is invalid.
            # Leave value as None, and continue
            pass
        index += 1

    del mapper
    return result


def toList(results, pickIndex = 0):
    """
    converts a list of tuples into a list, where pick index is the index in
    the tuple to use to prepare the list
    """
    returnData = [None] * len(results)
    index = 0
    for r in results:
        returnData[index] = r[pickIndex]
        index += 1
    del results
    return returnData


class Dictlist(dict):
    """
    Helper class which is a sub-class of dict class, where the values are stored as list, and new
    values assigned to an existing key appends the value at the end of the list
    """

    def __setitem__(self, key, value):
        try:
            self[key]
        except KeyError:
            super(Dictlist, self).__setitem__(key, [])
        self[key].append(value)
