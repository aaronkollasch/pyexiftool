# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import unittest
import exiftool
import warnings
import os
import shutil
import sys
import tempfile


class TestTagCopying(unittest.TestCase):
	def setUp(self):
		# Prepare exiftool.
		self.exiftool = exiftool.ExifTool()
		self.exiftool.start()

		# Prepare temporary directory for copy.
		directory = tempfile.mkdtemp(prefix='exiftool-test-')

		# Find example image.
		this_path = os.path.dirname(__file__)
		self.tag_source = os.path.join(this_path, 'rose.jpg')

		# Prepare path of copy.
		self.tag_target = os.path.join(directory, 'copy.jpg')

		# Copy image.
		shutil.copyfile(self.tag_source, self.tag_target)

		# Clear tags in copy.
		params = ['-overwrite_original', '-all=', self.tag_target]
		params_utf8 = [x.encode('utf-8') for x in params]
		self.exiftool.execute(*params_utf8)

	def test_tag_copying(self):
		tag = 'XMP:Subject'
		expected_value = 'Röschen'

		# Ensure source image has correct tag.
		original_value = self.exiftool.get_tag(tag, self.tag_source)
		self.assertEqual(original_value, expected_value)

		# Ensure target image does not already have that tag.
		value_before_copying = self.exiftool.get_tag(tag, self.tag_target)
		self.assertNotEqual(value_before_copying, expected_value)

		# Copy tags.
		self.exiftool.copy_tags(self.tag_source, self.tag_target)

		value_after_copying = self.exiftool.get_tag(tag, self.tag_target)
		self.assertEqual(value_after_copying, expected_value)


class TestExifTool(unittest.TestCase):

	#---------------------------------------------------------------------------------------------------------
	def setUp(self):
		self.et = exiftool.ExifTool(common_args=["-G", "-n", "-overwrite_original"])
	def tearDown(self):
		if hasattr(self, "et"):
			self.et.terminate()
		if hasattr(self, "process"):
			if self.process.poll() is None:
				self.process.terminate()
	#---------------------------------------------------------------------------------------------------------
	def test_termination_cm(self):
		# Test correct subprocess start and termination when using
		# self.et as a context manager
		self.assertFalse(self.et.running)
		self.assertRaises(ValueError, self.et.execute)
		with self.et:
			self.assertTrue(self.et.running)
			with warnings.catch_warnings(record=True) as w:
				self.et.start()
				self.assertEquals(len(w), 1)
				self.assertTrue(issubclass(w[0].category, UserWarning))
			self.process = self.et._process
			self.assertEqual(self.process.poll(), None)
		self.assertFalse(self.et.running)
		self.assertNotEqual(self.process.poll(), None)
	#---------------------------------------------------------------------------------------------------------
	def test_termination_explicit(self):
		# Test correct subprocess start and termination when
		# explicitly using start() and terminate()
		self.et.start()
		self.process = self.et._process
		self.assertEqual(self.process.poll(), None)
		self.et.terminate()
		self.assertNotEqual(self.process.poll(), None)
	#---------------------------------------------------------------------------------------------------------
	def test_termination_implicit(self):
		# Test implicit process termination on garbage collection
		self.et.start()
		self.process = self.et._process
		del self.et
		self.assertNotEqual(self.process.poll(), None)
	#---------------------------------------------------------------------------------------------------------
	def test_invalid_args_list(self):
		# test to make sure passing in an invalid args list will cause it to error out
		with self.assertRaises(TypeError):
			exiftool.ExifTool(common_args="not a list")
	#---------------------------------------------------------------------------------------------------------
	def test_get_metadata(self):
		expected_data = [{"SourceFile": "rose.jpg",
						  "File:FileType": "JPEG",
						  "File:ImageWidth": 70,
						  "File:ImageHeight": 46,
						  "XMP:Subject": "Röschen",
						  "Composite:ImageSize": "70 46"}, # older versions of exiftool used to display 70x46
						 {"SourceFile": "skyblue.png",
						  "File:FileType": "PNG",
						  "PNG:ImageWidth": 64,
						  "PNG:ImageHeight": 64,
						  "Composite:ImageSize": "64 64"}] # older versions of exiftool used to display 64x64
		script_path = os.path.dirname(__file__)
		source_files = []
		for d in expected_data:
			d["SourceFile"] = f = os.path.join(script_path, d["SourceFile"])
			self.assertTrue(os.path.exists(f))
			source_files.append(f)
		with self.et:
			actual_data = self.et.get_metadata_batch(source_files)
			tags0 = self.et.get_tags(["XMP:Subject"], source_files[0])
			tag0 = self.et.get_tag("XMP:Subject", source_files[0])
		for expected, actual in zip(expected_data, actual_data):
			et_version = actual["ExifTool:ExifToolVersion"]
			self.assertTrue(isinstance(et_version, float))
			if isinstance(et_version, float):    # avoid exception in Py3k
				self.assertTrue(
					et_version >= 8.40,
					"you should at least use ExifTool version 8.40")
			actual["SourceFile"] = os.path.normpath(actual["SourceFile"])
			for k, v in expected.items():
				self.assertEqual(actual[k], v)
		tags0["SourceFile"] = os.path.normpath(tags0["SourceFile"])
		self.assertEqual(tags0, dict((k, expected_data[0][k])
									 for k in ["SourceFile", "XMP:Subject"]))
		self.assertEqual(tag0, "Röschen")

	#---------------------------------------------------------------------------------------------------------
	def test_set_metadata(self):
		mod_prefix = "newcap_"
		expected_data = [{"SourceFile": "rose.jpg",
						  "Caption-Abstract": "Ein Röschen ganz allein"},
						 {"SourceFile": "skyblue.png",
						  "Caption-Abstract": "Blauer Himmel"}]
		script_path = os.path.dirname(__file__)
		source_files = []
		for d in expected_data:
			d["SourceFile"] = f = os.path.join(script_path, d["SourceFile"])
			self.assertTrue(os.path.exists(f))
			f_mod = os.path.join(os.path.dirname(f), mod_prefix + os.path.basename(f))
			self.assertFalse(os.path.exists(f_mod), "%s should not exist before the test. Please delete." % f_mod)
			shutil.copyfile(f, f_mod)
			source_files.append(f_mod)
			with self.et:
				self.et.set_tags({"Caption-Abstract":d["Caption-Abstract"]}, f_mod)
				tag0 = self.et.get_tag("IPTC:Caption-Abstract", f_mod)
			os.remove(f_mod)
			self.assertEqual(tag0, d["Caption-Abstract"])

	#---------------------------------------------------------------------------------------------------------
	def test_set_keywords(self):
		kw_to_add = ["added"]
		mod_prefix = "newkw_"
		expected_data = [{"SourceFile": "rose.jpg",
						  "Keywords": ["nature", "red plant"]}]
		script_path = os.path.dirname(__file__)
		source_files = []
		for d in expected_data:
			d["SourceFile"] = f = os.path.join(script_path, d["SourceFile"])
			self.assertTrue(os.path.exists(f))
			f_mod = os.path.join(os.path.dirname(f), mod_prefix + os.path.basename(f))
			self.assertFalse(os.path.exists(f_mod), "%s should not exist before the test. Please delete." % f_mod)
			shutil.copyfile(f, f_mod)
			source_files.append(f_mod)
			with self.et:
				self.et.set_keywords(exiftool.KW_REPLACE, d["Keywords"], f_mod)
				kwtag0 = self.et.get_tag("IPTC:Keywords", f_mod)
				kwrest = d["Keywords"][1:]
				self.et.set_keywords(exiftool.KW_REMOVE, kwrest, f_mod)
				kwtag1 = self.et.get_tag("IPTC:Keywords", f_mod)
				self.et.set_keywords(exiftool.KW_ADD, kw_to_add, f_mod)
				kwtag2 = self.et.get_tag("IPTC:Keywords", f_mod)
			os.remove(f_mod)
			self.assertEqual(kwtag0, d["Keywords"])
			self.assertEqual(kwtag1, d["Keywords"][0])
			self.assertEqual(kwtag2, [d["Keywords"][0]] + kw_to_add)


	#---------------------------------------------------------------------------------------------------------
	def test_executable_found(self):
		# test if executable is found on path
		save_sys_path = os.environ['PATH']

		if sys.platform == 'win32':
			test_path = "C:\\"
		else:
			test_path = "/"

		test_exec = exiftool.DEFAULT_EXECUTABLE
		
		# should be found in path as is
		self.assertTrue(exiftool.find_executable(test_exec, path=None))
		
		# modify path and search again
		self.assertFalse(exiftool.find_executable(test_exec, path=test_path))
		os.environ['PATH'] = test_path
		self.assertFalse(exiftool.find_executable(test_exec, path=None))
		
		# restore it
		os.environ['PATH'] = save_sys_path

#---------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
	unittest.main()
