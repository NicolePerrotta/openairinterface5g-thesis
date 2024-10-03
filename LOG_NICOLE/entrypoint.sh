#!/bin/sh
/oai-ran/cmake_targets/ran_build/build/nr-softmodem -O /oai-ran/vvdn-working_nicole.oai.conf --sa --thread-pool 1,3,5,7,9,11,13,15 --T_stdout 2 2>&1 | tee /LOG_NICOLE/oai.log
