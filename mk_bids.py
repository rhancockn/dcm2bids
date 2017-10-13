#!/usr/bin/python
import pandas
import dcm2niix
import sys
import os
import shutil
import dcm2niix
import numpy as np

bids_base = '/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/bids-raw'
subject_id = sys.argv[1]
session='time1'

gather_fname = os.path.join(bids_base, 'sub-%s/ses-%s/sub-%s_gather.tsv' % (subject_id, session, subject_id))

df = pandas.read_table(gather_fname)

#process each row
for i, row in df.iterrows():
	if (row.process != 1):
		continue
	intent = 'None'
	target_path = ''
	if row.modality == 'func':
		target_path = 'ses-%s/func/sub-%s_task-%s_acq-%s_run-%02d_%s' % (session, row.PatientID, row.task,row.acq,row.run,row.type)

	if row.modality == 'dwi':
		target_path = 'ses-%s/dwi/sub-%s_acq-%s_run-%02d_%s' % (session, row.PatientID, row.acq,row.run,row.type)
	
	if row.modality == 'T1w':
		target_path = 'ses-%s/anat/sub-%s_run-%02d_T1w' % (session, row.PatientID, row.run)

	if (row.modality == 'fmap') & (row.type in ['AP', 'PA']):
		target_path = 'ses-%s/fmap/sub-%s_acq-%s_dir-%s_run-%02d_epi' % (session, row.PatientID,row.acq,row.type,row.run)

	if (row.modality == 'fmap') & (row.type in ['magnitude', 'magnitude1', 'magnitude2', 'phasediff']):
		target_path = 'ses-%s/fmap/sub-%s_run-%02d_%s' % (session, row.PatientID,row.run, row.type)

	if row.modality == 'fmap':
		intent =[]
		idxs = eval(row.for_idxs)
		for j in idxs:
			intent = intent + [df.loc[j,'target_path']+'.nii.gz']


	df.set_value(i, 'target_path', target_path)

	#try:
	d2n = dcm2niix.dcm2niix(row, bids_base, intent)
	d2n.process()
	#except:
	#	print('--------------------\n\nError processing:')
	#	print(row)
	#	print('--------------------\n\n')


	if row.type == 'bold':
		eprime_fname = '/Volumes/PEGASUS/Projects/BilingualR01/ImagingData/IncomingBx/time1/split/%s' % row.eprime
		if os.path.isfile(eprime_fname):
			shutil.copyfile(eprime_fname, 
				os.path.join(bids_base,'sub-' + subject_id, os.path.dirname(row.target_path), row.eprime))
		else:
			print('WARNING: no %s' % row.eprime)

df.to_csv(gather_fname, sep='\t')





