import os
import subprocess
import unittest
import filecmp

class TestBuildScript(unittest.TestCase):
    def test90(self):
        testPassed = True
        message = 'a test case was not found :( -- bc this is extra credit we are hiding the test directory names'
        #output = subprocess.Popen(["./test_fsrecursive_bash.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #rec = output.stdout.read().decode('utf-8').strip()
        output = subprocess.Popen(["./test_fsrecursive_c.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rec = output.stdout.read().decode('utf-8').strip()
        folders = ['labs','bin','xyz','www','etc','var','homework','asd','super']
        folders_found = 0
        for folder in folders:
            if folder in rec:
                folders_found += 1
            else:
                testPassed = False
        print(f'We found {folders_found}/{str(len(folders))} folder names from our special test directory.')
        self.assertTrue(testPassed, message)

if __name__ == '__main__':
    unittest.main()