#!/usr/bin/python
#Prepare scans for relabelling
from os import listdir
from os.path import isdir, isfile, join
import pandas
import numpy as np
import glob
import dicom
from collections import defaultdict
import sys
import os
import errno    
import datetime

#ignore the UserWarning we get with CSA
import warnings
warnings.filterwarnings('ignore', category=UserWarning, append=True)
import nibabel.nicom.csareader as csa
import nibabel.nicom.dicomreaders as dcmreaders
import nibabel.nicom.dicomwrappers as dcmwrappers

session = 'time1'
error_name=''

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

subject_id = sys.argv[1]
dicom_dict = pandas.read_csv('dicom_dict.csv')
dicom_path=glob.glob('/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/Incoming/%s/Hoeft*' % subject_id)
if len(dicom_path) !=1:
	raise Exception('Zero or Multiple DICOM directories for %s!' % subject_id)

dicom_path = dicom_path[0]

df_run = pandas.DataFrame()

dirs = [d for d in listdir(dicom_path) if isdir(join(dicom_path,d))]
ProtocolName = []
SeriesNumber = []
AcquisitionTime = []
AcquisitionDate = []
nimages = []
PatientID = []
PatientName = []
DICOMPath = []
EchoTime = []
InPlanePhaseEncodingDirection = []
ImageType = []
MB = []
PhaseEncodingDirectionPositive = []
for d in dirs:
	#fieldmaps are sometimes stored in the same sequence-this will glob only 1 echo
	#this gets handled later in the dicom conversion
	imgs = glob.glob(join(dicom_path,d,'IM-*[0-9]*.dcm'))
	imgs.sort()

	if len(imgs) >0:
		dcm = dicom.read_file(imgs[0])
		dcm_w = dcmwrappers.wrapper_from_file(imgs[0])
		if ('ORIGINAL' in dcm.ImageType) and ('CSA REPORT' not in dcm.ImageType): 
			nimages = nimages + [len(imgs)]
			ProtocolName = ProtocolName + [dcm.ProtocolName]
			SeriesNumber = SeriesNumber + [int(dcm.SeriesNumber)]
			AcquisitionDate = AcquisitionDate + [int(dcm.AcquisitionDate)]
			AcquisitionTime = AcquisitionTime + [float(dcm.AcquisitionTime)]
			PatientID = PatientID +[dcm.PatientID]
			PatientName = PatientName + [dcm.PatientName]
			DICOMPath = DICOMPath + [join(dicom_path,d)]
			EchoTime = EchoTime + [float(dcm.EchoTime)]
			if 'InPlanePhaseEncodingDirection' in dcm.dir():
				InPlanePhaseEncodingDirection = InPlanePhaseEncodingDirection + [dcm.InPlanePhaseEncodingDirection]
			else:
				InPlanePhaseEncodingDirection = InPlanePhaseEncodingDirection + [np.nan]

			ImageType = ImageType +[dcm.ImageType[2]] #encodes whether the image is (P)hase or (M)agnitude
			MB = MB + [dcm.ImageType[3]]
			pep = dcm_w.csa_header['tags'][u'PhaseEncodingDirectionPositive']['items']
			if len(pep) >0:
				PhaseEncodingDirectionPositive = PhaseEncodingDirectionPositive + pep
			else:
				PhaseEncodingDirectionPositive = PhaseEncodingDirectionPositive + [np.nan]



df_run = pandas.DataFrame(data={'AcquisitionDate': AcquisitionDate, 'AcquisitionTime': AcquisitionTime, 'ProtocolName': ProtocolName, 'SeriesNumber': SeriesNumber, 'PatientID': PatientID, 'PatientName': PatientName, 'nimages':nimages, 'DICOMPath': DICOMPath, 'EchoTime': EchoTime, 'InPlanePhaseEncodingDirection': InPlanePhaseEncodingDirection, 'PhaseEncodingDirectionPositive': PhaseEncodingDirectionPositive, 'ImageType': ImageType, 'MB': MB})
df_run['process'] = np.nan #whether this dataset should be processed, basiclaly if we have figured out what it is
df_run['type'] = '' #fmri, T1, DWI_SB, DWI_MB, fieldmap
df_run['task'] = '' #type or the task
df_run['for'] = '' #series the fieldmap or phase ecnode should be associated with. Automaticlaly assigned, should be checked
df_run['run'] = np.nan
df_run['acq'] = ''
df_run['modality'] = ''
df_run['for_idxs'] = ''
df_run['target_path'] = ''
df_run['eprime'] = ''
df_run=df_run.sort(['AcquisitionDate', 'AcquisitionTime', 'SeriesNumber'])
df_run=df_run.reset_index()

## determine image types
for i, row in df_run.iterrows():
	dict_row = dicom_dict[(dicom_dict.MB == row.MB) & (dicom_dict.ImageType == row.ImageType) & (dicom_dict.ProtocolName == row.ProtocolName) & (dicom_dict.EchoTime == row.EchoTime) & (dicom_dict.nimages == row.nimages)]
	df_run.set_value(i, 'process',dict_row.shape[0]) #process will > 1 if the image is ambiguous
	


	if not (row.PatientID == row.PatientName == subject_id):
		raise Exception('Inconsistent subject ID, patient ID or patient name for %s' % subject_id)

	if dict_row.shape[0]==1:
		df_run.set_value(i,'modality',dict_row.modality.values[0])
		df_run.set_value(i,'type',dict_row.type.values[0])
		df_run.set_value(i,'task',dict_row.task.values[0])
		df_run.set_value(i,'acq',dict_row.acq.values[0])
		df_run.set_value(i,'for',dict_row['for'].values[0])

		#processing for sbrefs is conditional on finding an associted bold sequence
		if dict_row.type.values[0] == 'sbref':
			df_run.set_value(i, 'process',0)



#assign runs
run_numbers = defaultdict(int)
last_fmap = np.nan
dwi_idxs = [];
func_idxs = [];
last_modality = '';
itr = df_run.iterrows()
for i, row in itr:
	#track rows that might have associated fieldmaps
	if (row.modality != last_modality) & ((row.process==1) | (row.InPlanePhaseEncodingDirection=='ROW')):
		last_modality = row.modality
		if row.modality != 'fmap':
			dwi_idxs = [];
			func_idxs = [];

	if row.process == 1:		
		if row.modality == 'func':
			func_idxs = func_idxs + [i]

		if row.modality == 'dwi':
			dwi_idxs = dwi_idxs + [i]

	## Task fMRI
	if row.type == 'bold':
		run_numbers[row.task] = run_numbers[row.task] + 1
		df_run.set_value(i,'run',run_numbers[row.task])
		df_run.set_value(i, 'target_path', 'ses-%s/func/sub-%s_task-%s_acq-%s_run-%02d_bold' % (session, row.PatientID, row.task,row.acq,run_numbers[row.task]))
		if row.acq == 'multiband': #find the SBRef, die if we don't
			if (df_run.loc[i-1,'type']=='sbref') & (df_run.loc[i-1,'SeriesNumber']==row.SeriesNumber-1):
				df_run.set_value(i-1,'run',run_numbers[row.task])
				df_run.set_value(i-1,'process',1)
				df_run.set_value(i-1, 'target_path', 'ses-%s/func/sub-%s_task-%s_acq-%s_run-%02d_sbref' % (session, row.PatientID, row.task,row.acq,run_numbers[row.task]))

		eprime = 'sub-%s_ses-%02d_task-%s_eprime.tsv' % (row.PatientID, run_numbers[row.task], row.task)
		eprime_path = os.path.join('/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/IncomingBx/time1/split/',eprime)
		if os.path.isfile(eprime_path):
			df_task = pandas.read_table(eprime_path)
			task_start_delay = float(df_task['ReadyGo.RTTime'][0])/1000.0
			task_start = datetime.datetime.strptime(df_task.SessionDate[0]+ ' ' + df_task.SessionTime[0], "%m-%d-%Y %H:%M:%S")
			trigger_start = task_start + datetime.timedelta(seconds=task_start_delay)

			scan_start = datetime.datetime.strptime(str(row.AcquisitionDate)+ ' ' + str(row.AcquisitionTime), "%Y%m%d %H%M%S.%f")
			delta = trigger_start-scan_start
			if np.abs(delta.total_seconds()) > 60:
				print('info: task-scan time delta is %f seconds (%s %s-%s)' % (delta.total_seconds(), subject_id, row.task,run_numbers[row.task]))
			if np.abs(delta.total_seconds()) > 120:
				print('WARNING: task-scan time delta is %f seconds (%s %s-%s). Not marking eprime for copy!' % (delta.total_seconds(), subject_id, row.task,run_numbers[row.task]))
				error_name = '_eprime'
			else:
				df_run.set_value(i, 'eprime', eprime)
		else:
			print('WARNING: EPRIME %s not found' % eprime)
			error_name = '_eprime'

	##diffusion
	if row.type == 'dwi':
		run_numbers[row.type] = run_numbers[row.type] + 1
		df_run.set_value(i,'run',run_numbers[row.type])
		df_run.set_value(i, 'target_path', 'ses-%s/dwi/sub-%s_acq-%s_run-%02d_dwi' % (session, row.PatientID, row.acq,run_numbers[row.type]))
		if row.acq == 'multiband': #find the SBRef, die if we don't
			if (df_run.loc[i-1,'type']=='sbref') & (df_run.loc[i-1,'SeriesNumber']==row.SeriesNumber-1):
				df_run.set_value(i-1,'run',run_numbers[row.type])
				df_run.set_value(i-1,'process',1)
				df_run.set_value(i-1, 'target_path', 'ses-%s/dwi/sub-%s_acq-%s_run-%02d_sbref' % (session, row.PatientID, row.acq,run_numbers[row.type]))

	##T1
	if row.type == 'T1w':
		run_numbers[row.type] = run_numbers[row.type] + 1
		df_run.set_value(i,'run',run_numbers[row.type])
		df_run.set_value(i, 'target_path', 'ses-%s/anat/sub-%s_run-%02d_T1w' % (session, row.PatientID, run_numbers[row.type]))

	##fieldmaps
	if (row.modality == 'fmap'):
		run_numbers[row.modality] = run_numbers[row.modality] + 1
		while row.type in ['AP', 'PA']:
			df_run.set_value(i,'run',run_numbers[row.modality])
			df_run.set_value(i, 'target_path', 'ses-%s/fmap/sub-%s_acq-%s_dir-%s_run-%02d_epi' % (session, row.PatientID,row.acq,row.type,run_numbers[row.modality]))
			if row['for'] == 'dwi':
				df_run.set_value(i,'for_idxs',str(dwi_idxs))
			if row['for'] == 'func':
				df_run.set_value(i,'for_idxs',str(func_idxs))
			if (i+1 < df_run.shape[0]) and (df_run.loc[i+1,'type'] in ['AP', 'PA']):
				i,row = itr.next()
			else:
				break

		while row.type in ['magnitude', 'magnitude1', 'magnitude2', 'phasediff']:
			df_run.set_value(i,'run',run_numbers[row.modality])
			df_run.set_value(i, 'target_path', 'ses-%s/fmap/sub-%s_run-%02d_%s' % (session, row.PatientID,run_numbers[row.modality], row.type))
			if row['for'] == 'dwi':
				df_run.set_value(i,'for_idxs',str(dwi_idxs))
			if row['for'] == 'func':
				df_run.set_value(i,'for_idxs',str(func_idxs))

			if (i+1 < df_run.shape[0]) and (df_run.loc[i+1,'type'] in ['magnitude', 'magnitude1', 'magnitude2', 'phasediff']):
				i,row= itr.next()
			else:
				break


#check that functional runs and eprime logs match up
df_bold = df_run[df_run.type=='bold']
run_counts = df_bold[['task', 'run']].groupby(['task']).max()
run_counts.reset_index(inplace=True)
for i, row in run_counts.iterrows():
	if row.task:
		eprimes = glob.glob(os.path.join('/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/IncomingBx/time1/split/','sub-%s_ses-*_task-%s_eprime.tsv' % (subject_id, row.task)))
		if len(eprimes) != row.run:
			print('WARNING: Mismatch between runs and eprime files (%s %s)' % (subject_id, row.task))
			error_name = '_eprime'

mkdir_p('/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/bids-raw/sub-%s/ses-%s/' % (subject_id,session))
df_run.to_csv('/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/bids-raw/sub-%s/ses-%s/sub-%s_gather%s.tsv' % (subject_id,session,subject_id, error_name), sep='\t')

