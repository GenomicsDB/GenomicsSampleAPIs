import requests
import json
import uuid
import os
import sys
from datetime import datetime
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from metadb.api import DBImport, DBQuery
import metadb.models as models

now = datetime.now
NUM_RETRIES = 10

class ConstTileFields(OrderedDict):
    """
    OrderedDict wrapper for constant TileDB fields
    """
    def __init__(self):
        super(ConstTileFields, self).__init__()
        self["END"] = {"vcf_field_class": ["INFO"], "type": "int"}
        self["BaseQRankSum"] = {"vcf_field_class": ["INFO"], "type": "float"}
        self["ClippingRankSum"] = {"vcf_field_class": ["INFO"], "type": "float"}
        self["MQRankSum"] = {"vcf_field_class": ["INFO"], "type": "float"}
        self["ReadPosRankSum"] = {"vcf_field_class": ["INFO"], "type": "float"}
        self["MQ"] = {"vcf_field_class": ["INFO"], "type": "float"}
        self["MQ0"] = {"vcf_field_class": ["INFO"], "type": "int"}
        self["AF"] = {"vcf_field_class": ["INFO"], "type": "float", "length": "A"}
        self["AN"] = {"vcf_field_class": ["INFO"], "type": "int", "length": 1}
        self["AC"] = {"vcf_field_class": ["INFO"], "type": "int", "length": "A"}
        self["DP"] = {"vcf_field_class": ["INFO", "FORMAT"], "type": "int"}
        self["MIN_DP"] = {"vcf_field_class": ["FORMAT"], "type": "int"}
        self["GQ"] = {"vcf_field_class": ["FORMAT"], "type": "int"}
        self["SB"] = {"vcf_field_class": ["FORMAT"], "type": "int", "length": 4}
        self["AD"] = {"vcf_field_class": ["FORMAT"], "type": "int", "length": "R"}
        self["PL"] = {"vcf_field_class": ["FORMAT"], "type": "int", "length": "G"}
        self["GT"] = {"vcf_field_class": ["FORMAT"], "type": "int", "length": "P"}
        self["PS"] = {"vcf_field_class": ["FORMAT"], "type": "int", "length": 1}


def getReference(assembly, chromosome, start, end):
    """
    Gets the Reference string from rest.ensemble.org
    """
    # Ensemble takes MT and not M
    if(chromosome == "M"):
        chromosome = "MT"
    server = "http://rest.ensembl.org"
    request = "/sequence/region/human/" + chromosome + ":" + \
        str(start) + ".." + str(end) + ":1?coord_system_version=" + assembly

    nRetires = NUM_RETRIES
    r = None
    while(nRetires):
        bFail = False
        try:
            r = requests.get(server + request,
                             headers={"Content-Type": "text/plain"})
        except Exception as e:
            bFail = True

        if r is None or not r.ok or bFail:
            nRetires -= 1
            bFail = False

            # Use a sleep timer if we are failing
            import time
            time.sleep(nRetires)
            continue
        else:
            break
    if r is None or not r.ok or bFail:
        print server + request
        r.raise_for_status()

    return r.text


def getFileName(inFile, splitStr=None):
    """
    Strips the /'s and gets the file name without extension
    """
    if(splitStr is None or not inFile.endswith(splitStr)):
        splitStr = "."
    fileName = os.path.basename(inFile).split(splitStr)[0]
    return fileName


def getFilePointer(fileName, gzipped, mode):
    """
    returns a file pointer given the name, type and mode
    """
    if(gzipped):
        import gzip
        return gzip.open(fileName, mode)
    else:
        return open(fileName, mode)


def writeJSON2File(input_json, output_file):
    with open(output_file, "w") as outFP:
        json.dump(input_json, outFP, indent=2, separators=(',', ': '))


def writeVIDMappingFile(DB_URI, reference_set_id, output_file, fields_dict=ConstTileFields()):
    """
    Creates the VID mapping file for GenomicsDB import.
    """
    with DBQuery(DB_URI).getSession() as metadb:
        # grab references with tiledb offset from metadb
        references = metadb.session.query(models.Reference)\
            .filter(models.Reference.reference_set_id == reference_set_id)\
            .all()

        vid_mapping = OrderedDict()
        vid_mapping["fields"] = fields_dict
        vid_mapping["contigs"] = OrderedDict()
        contigs = vid_mapping["contigs"]
        for reference in references:
            contigs[
                reference.name] = {
                "length": reference.length,
                "tiledb_column_offset": reference.tiledb_column_offset}

        writeJSON2File(vid_mapping, output_file)


def registerWithMetadb(config, references=None):
    """
    Registers parent object of a callset in metadb for both MAF and VCF importing.
    """
    if references is None:
        # set MAF specific vars
        with open(config.TileDBAssembly) as config_file:
            assemb_info = json.load(config_file)

        assembly = assemb_info['assembly']
        workspace = config.TileDBSchema['workspace']
        array = config.TileDBSchema['array']
        references = assemb_info['chromosome']

        dbimport = DBImport(config.DB_URI)

    else:
        # set VCF specific vars
        assembly = config['assembly']
        workspace = config['workspace']
        array = config['array']
        dbimport = DBImport(config['dburi'])

    with dbimport.getSession() as metadb:
        # register workspace, referenceset, array, and variantset
        ws = metadb.registerWorkspace(
            str(uuid.uuid4()), workspace)
        rs = metadb.registerReferenceSet(
            str(uuid.uuid4()), 
            assembly, 
            references=references)
        dba = metadb.registerDBArray(
            guid=str(uuid.uuid4()),
            name=array,
            reference_set_id=rs.id,
            workspace_id=ws.id)
        vs = metadb.registerVariantSet(
            guid=str(uuid.uuid4()),
            reference_set_id=rs.id,
            dataset_id=os.path.basename(workspace))

    return dba, vs, rs


def createMappingFiles(outputDir, callset_mapping, rs_id, DB_URI, combinedOutputFile=None):
    """
    Creates Callset mapping and VID mapping file required for GenomicsDB loading.
    """
    
    baseFileName = ''
    if combinedOutputFile:
        baseFileName = getFileName(combinedOutputFile)+"."

    callset_mapping_file = os.path.join(outputDir, "{}callset_mapping".format(baseFileName))
    writeJSON2File(callset_mapping, callset_mapping_file)
    print "Generated Call Set Mapping File : {0}".format(callset_mapping_file)

    vid_mapping_file = os.path.join(outputDir, "{}vid_mapping".format(baseFileName))
    writeVIDMappingFile(DB_URI, rs_id, vid_mapping_file)
    print "Generated VID Mapping File : {0}".format(vid_mapping_file)


def log(outString):
    print "{0}: {1}".format(now(), outString)


def progressPrint(outString):
    sys.stdout.write("\r" + outString)
    sys.stdout.flush()
