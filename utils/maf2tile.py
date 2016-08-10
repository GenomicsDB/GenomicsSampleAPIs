#!/usr/bin/env python

import subprocess
import utils.maf_importer as multiprocess_import
import utils.helper as helper

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Convert  MAF format to Tile DB CSV")

    parser.add_argument(
        "-c", 
        "--config", 
        required=True, 
        type=str,
        help="input configuration file for MAF conversion")
    
    parser.add_argument(
        "-d",
        "--outputdir",
        required=True,
        type=str,
        help="Output directory where the outputs need to be stored")
    
    parser.add_argument(
        "-i",
        "--inputs",
        nargs='+',
        type=str,
        required=True,
        help="List of input MAF files to convert")

    parser.add_argument(
        "-z",
        "--gzipped",
        action="store_true",
        required=False,
        help="True/False indicating if the input file is a gzipped file or not")

    parser.add_argument(
        "-s",
        "--spark",
        action="store_true",
        help="Run as spark.")

    parser.add_argument(
        "-o",
        "--output",
        required=False,
        type=str,
        help="output Tile DB CSV file (without the path) which will be stored in the output directory. Required for spark.")

    parser.add_argument(
        "-a",
        "--append_callsets",
        required=False,
        type=str,
        help="CallSet mapping file to append.")

    parser.add_argument(
        "-l",
        "--loader",
        required=False,
        type=str,
        help="Loader JSON to load data into Tile DB.")

    args = parser.parse_args()

    if args.spark:
        # call spark from within import script
        # output file is required
        if args.output:
            spark_cmd = [
                "spark-submit", 
                "maf_pyspark.py", 
                "-c", args.config, 
                "-d", args.outputdir, 
                "-o", args.output, 
                "-i"]

            spark_cmd.extend(args.inputs)
            if args.loader:
                spark_cmd.extend(['-l', args.loader])
            if args.append_callsets:
                spark_cmd.extend(['-a', args.append_callsets])
            print spark_cmd
            if subprocess.call(spark_cmd) != 0:
                raise Exception("Error running converter")
        else:
            print """
            usage: maf2tile.py [-h] -c CONFIG -d OUTPUTDIR -i INPUTS
                   [INPUTS ...] [-z] [-s] [-o OUTPUT] [-l LOADER]
            maf2tile.py: error: argument -o/--output is required when -s is sets
            """
    else:

        multiprocess_import.parallelGen(
            args.config,
            args.inputs,
            args.outputdir,
            args.gzipped,
            callset_file=args.append_callsets,
            loader_config=args.loader)
