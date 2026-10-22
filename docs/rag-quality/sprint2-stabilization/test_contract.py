import unittest
from copy import deepcopy
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from validate_contract import validate,read,PACKAGE

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.folder=PACKAGE/'contracts/2.0.0'
        self.contract=read(self.folder/'contract.json')
    def test_valid_contract_keeps_human_acceptance_pending(self):
        self.assertIsNone(validate(self.contract,self.folder)['human_acceptance'])
    def test_mismatched_historical_hash_rejected(self):
        self.contract['baseline']['dataset_sha256']='0'*64
        with self.assertRaises(AssertionError): validate(self.contract,self.folder)
    def test_cross_version_equivalence_rejected(self):
        self.contract['scoring_policy']['cross_version_equivalence']=True
        with self.assertRaises(AssertionError): validate(self.contract,self.folder)
    def test_automatic_human_decision_rejected(self):
        self.contract['review_protocol']['decision']='approved'
        with self.assertRaises(AssertionError): validate(self.contract,self.folder)
    def test_missing_explicit_topic_rejected(self):
        self.contract['inputs']['FP-05']={}
        with self.assertRaises(AssertionError): validate(self.contract,self.folder)
    def test_historical_version_cannot_replace_runtime_version(self):
        self.contract['source_bindings'][0]['runtime_version']='snapshot-local-v1'
        with self.assertRaises(AssertionError): validate(self.contract,self.folder)

if __name__=='__main__': unittest.main()
