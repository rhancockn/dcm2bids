#!/use/bin/python
import tempfile
import os
import dicom
import pandas
import json
import numpy as np
from os.path import join
import glob
import errno    
import shutil

class dcm2niix(object):
	"""A wrapper for the dcm2niix command
	"""
	def __init__(self, row, bids_dir, intent = None):
		self.intent = intent
		#Dicom keys of interest
		self.keys=['RepetitionTime', 'AcquisitionMatrix', 'EchoTime', 'EchoTrainLength','FlipAngle', 'Manufacturer', 'ManufacturerModelName', 'MagneticFieldStrength', 'DeviceSerialNumber', 'SoftwareVersions', 'InversionTime', 'PixelBandwidth', 'ScanOptions', 'InPlanePhaseEncodingDirection']
		self.wd = os.getcwd()
		self.row = row
		self.bids_basename = join(bids_dir, 'sub-' + row.PatientID, row.target_path)

		files = glob.glob(join(row.DICOMPath, 'IM-*-0001.dcm'))
		self.dcm = dicom.read_file(files[0])


	#def __del__(self):
	#	os.rmdir(self.tempdir)


	def _make_dicom_json(self):
		self.json_dict = {}
		keys = np.intersect1d(self.keys,self.dcm.dir())
		for k in keys:
			self.json_dict[k] = self.dcm.get(k)
			if self.dcm.has_key((0x19,0x1028)):
				self.json_dict['EffectiveEchoSpacing'] = 1.0/(self.dcm[0x19,0x1028].value*self.dcm.AcquisitionMatrix[0])
				self.json_dict['TotalReadoutTime'] = 1.0/self.dcm[0x19,0x1028].value
			if self.dcm.has_key((0x19,0x1029)):
				self.json_dict['SliceTiming'] = self.dcm[0x19,0x1029].value 

			self.json_dict['PulseSequenceDetails'] = self.dcm[0x18,0x24].value
			if self.dcm.has_key((0x20,0x4000)):
				self.json_dict['PulseSequenceDetails'] = self.json_dict['PulseSequenceDetails'] + ' ' + self.dcm[0x20,0x4000].value 

			if self.dcm.has_key((0x51,0x100f)):
				self.json_dict['ReceiveCoilName'] = self.dcm[0x51,0x100f].value
				
			self.json_dict['TaskName'] = self.row.task
			self.json_dict['PhaseEncodingDirectionPositive'] = self.row.PhaseEncodingDirectionPositive

			#add the list of intent scans, if any. 
			if self.intent:
				self.json_dict['IntendedFor'] = self.intent


	def _convert(self):
		self.tempdir = tempfile.mkdtemp()
		cmd = 'dcm2niix -b y -o . -z y -x n -f out "%s"' % self.row.DICOMPath
		os.chdir(self.tempdir)
		err = os.system(cmd)
		if err != 0:
			raise Exception('Error converting DICOM %s' % self.row.DICOMPath)

		os.chdir(self.wd)

	def _copy(self):
		bids_dir = os.path.dirname(self.bids_basename)
		self._mkdir_p(bids_dir)

		#the magnitudes from both echoes are in the same directory
		#dcm2niix splits the echoes. Copy them appropriately
		if self.row.type == 'magnitude':
			if os.path.isfile(join(self.tempdir,'out.nii.gz')):
				shutil.copyfile(join(self.tempdir,'out.nii.gz'), self.bids_basename + '1.nii.gz')
			if os.path.isfile(join(self.tempdir,'_e2out.nii.gz')):	
				shutil.copyfile(join(self.tempdir,'_e2out.nii.gz'), self.bids_basename + '2.nii.gz')
			
			if os.path.isfile(join(self.tempdir,'out.bids')):
				json_fname = self.bids_basename + '1.json'
				shutil.copyfile(join(self.tempdir,'out.bids'), json_fname)
				self._update_json(json_fname)

			json_fname = self.bids_basename + '2.json'
			shutil.copyfile(join(self.tempdir,'_e2out.bids'), json_fname)
			self._update_json(json_fname)

		elif self.row.type in ['phasediff', 'magnitude2']:
			shutil.copyfile(glob.glob(join(self.tempdir,'*out.nii.gz'))[0], self.bids_basename + '.nii.gz')
			json_fname = self.bids_basename + '.json'
			shutil.copyfile(glob.glob(join(self.tempdir,'*out.bids'))[0], json_fname)
			self._update_json(json_fname)


		#anything but a single magnitude directory should produce one out.nii.gz/out.bids pair
		else:
			imgs = glob.glob(join(self.tempdir, '*out*.nii.gz'))
			if len(imgs) > 1:
				raise Exception('More out.nii.gz files than expected')

			shutil.copyfile(join(self.tempdir,'out.nii.gz'), self.bids_basename + '.nii.gz')

			json_fname = self.bids_basename + '.json'
			shutil.copyfile(join(self.tempdir,'out.bids'), json_fname)
			self._update_json(json_fname)


		if self.row.type == 'dwi':
			shutil.copyfile(join(self.tempdir,'out.bval'), self.bids_basename + '.bval')
			shutil.copyfile(join(self.tempdir,'out.bvec'), self.bids_basename + '.bvec')
			

		

	def _update_json(self, fname):
		fp=open(fname, 'r+')
		meta = json.load(fp)
		orig_keys	= np.intersect1d(self.json_dict.keys(), meta.keys())
			
		for k in np.setdiff1d(self.json_dict.keys(),meta.keys()):
			meta[k]=self.json_dict[k]

		for k in orig_keys:
			meta['o'+k] = self.json_dict[k]

		fp.seek(0)
		json.dump(meta,fp,indent=2)
		fp.close()

	def _mkdir_p(self,path):
	    try:
	        os.makedirs(path)
	    except OSError as exc:  
	        if exc.errno == errno.EEXIST and os.path.isdir(path):
	            pass
	        else:
	            raise

	def process(self):
		self._make_dicom_json()
		self._convert()
		self._copy()
		os.system('chmod 2550 %s*' % self.bids_basename)
		shutil.rmtree(self.tempdir)




