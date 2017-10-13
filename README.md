#Label DICOMS and check task data
The first step of the MR processing pipeline is to identify what each DICOM files corresponds to, verify that the subject_id, PatientID and Patient Name match and match up E-prime output files with the DICOMs.

The main command is

`gather_dicoms.py subject_id`

This will generate a data file that lists key features of each DICOM series and which modality, task and run the series should correspond to. 

##DICOM matching template

The `dicom_dict.csv` file provides a template for identifying scans based on the ProtocolName and DICOM tags. Each possible scan should be uniquely identified by a single row. The fields marked *ID* in the table below are used to identify the scan and associate it with the information in the *meta* fields.

Field | Content | Tag |ID/meta|Description
------|---------|-----|------|---------
ImageType | String| |ID| The XXX element of the
EchoTime | float (ms) || ID| The echo time
MB | String | |ID| The XXX elment of
ProtocolName | String | |ID|The name of the protocl
nimages |int | n/a|ID|The number of DICOM files in the folder for this series
modality | String: T1w, dwi, fmap, func| n/a |meta|
type | String: T1w, sbref, dwi, AP,PA, magnitude[12]*, phasediff, bold | n/a |meta|
task | String: {cn,en,sp}{pma,wma,wmv,sma} | n/a|meta
acq | String: multiband, singleband | n/a|meta
for | String: dwi, func| n/a |meta

##Matching
The script iterates through directories and uses all of the ID fields (read from a single DICOM file, which should not be assumed to be the first file in the directory) and the number of files in a directory to identify the series.

###Assigning runs



##Sanity Checks and Errors
###Subject ID
The script will raise an exception and terminate if any of (1) the subject_id passed on the command line; (2) PatientID; and (3) PatientName are not identical.

The solution to this is to:

1. Review the AcquisitionDate and AcquisitionTime fields in the DICOMS
2. Review the scan schedule and log sheets to determine which subject should have been in the scanner at the time of acquisition
3. Rename the subject folder and/or edit the DICOM fields

To edit the fields:

1. Create a new folder for the DICOM export directories based on the existing folder with the suffix _Remapped
2. Use DicomBrowser to correct the field(s), storing the corrected files in this new folder
3. Rename the original folder by adding the prefix Orig_

### Multiple Sessions
The folder structure for raw data is assumed to be of the form BILNNNN/Hoeftxxxx/series/\*.dcm. Multiple *Hoeft\** directories will raise an exception. These directories should be merged.

### Tasks
For scans of type *bold*, the gather script attempts to match the scan to a processed eprime log file by

- Searching for an eprime file for the same subject, run and task
- Checking that the runtime of the script and the AcquisitionDate/AcquistionTime are close (within 120secs)
- Checking that there are the same number of *bold* and eprime runs for each task

If any of these conditions fail, the script will generate a warning and suffix the output with *_eprime*. If the time difference is >60 seconds, an information message will be printed. In practice, the stimulus computer and scanner clocks appear to be 50-100secs apart.


##Output 

##Fieldmaps (phase-magnitude sets)
DICOMS for magnitude images appear to be inconsistently exported in two different ways:

- A single directory containing both echoes (IM\*-0001.dcm and IM\*-0002.dcm)
- Two directories, one for each echo, having the same series number

The reconstructed phase difference is always in a separate directory. Currently, this is handled by having 5 entries for every fieldmap (for historical reasons):

1. EchoTime = TE1; nimages = #slices; type = magnitude1
2. EchoTime = TE2; nimages = #slices; type = magnitude2
3. EchoTime = TE1; nimages = 2*#slices; type = magnitude
4. EchoTime = TE2; nimages = 2*#slices; type = magnitude
5. EchoTime = TE2; nimages = #slices; type = phasediff

If 3 or 4 are matched, we rely on dcm2niix (the command) to separate the echoes and use further hacks in `mk_bids` and `dcm2niix`

#Convert DICOMs to bids-raw

`mk_bids.py subject_id`




