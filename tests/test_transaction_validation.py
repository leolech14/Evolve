import unittest
from transaction_validator import validate_transaction

class TestTransactionValidation(unittest.TestCase):
    def test_special_format_parsing(self):
        """Test various special transaction format cases"""
        # Test mixed format with special characters
        result = validate_transaction("TX-2023/SP-001|USER:john.doe|AMT:$1,234.56|TYPE:SPECIAL|DESC:Test & Validation")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 1234.56)

        # Test multi-line format
        multi_line_tx = """TX-2023/SP-002
USER:jane.smith
AMT:€2,345.67
TYPE:MULTI_LINE
DESC:Multiple\nLine\nTransaction"""
        result = validate_transaction(multi_line_tx)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 2345.67)

        # Test JSON-like format
        result = validate_transaction('TX-2023/SP-003|{"user":"bob.jones","amount":"¥5000","type":"JSON_LIKE","desc":"JSON format test"}')
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 5000)

    def test_complex_international(self):
        """Test complex international transaction formats"""
        # Test European format
        result = validate_transaction("TX-2023/INT-001|USER:hans.mueller|AMT:€1.000.000,00|TYPE:LARGE_EU|DESC:European large amount")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 1000000.00)

        # Test Arabic format
        result = validate_transaction("TX-2023/INT-002|USER:ahmed.hassan|AMT:١٢٣٤٥.٦٧|TYPE:ARABIC|DESC:Arabic format transaction تحويل")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 12345.67)

        # Test Indian format
        result = validate_transaction("TX-2023/INT-004|USER:raj.patel|AMT:₹1,23,45,678.90|TYPE:INR|DESC:Indian format with lakhs")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 12345678.90)

    def test_encoding_variants(self):
        """Test various encoding scenarios"""
        # Test UTF-8 BOM
        result = validate_transaction("\uFEFFTX-2023/ENC-001|USER:maria.garcía|AMT:$100.00|TYPE:UTF8_BOM|DESC:BOM test case")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 100.00)

        # Test emoji in description
        result = validate_transaction("TX-2023/ENC-003|USER:james.smith|AMT:$200.00|TYPE:EMOJI|DESC:Payment for 🎉 party 🎈")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 200.00)

        # Test mixed encoding
        result = validate_transaction("TX-2023/ENC-004|USER:софія.коваль|AMT:₴300.00|TYPE:MIXED_ENC|DESC:Український опис 💰")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.amount, 300.00)

    def test_invalid_format_handling(self):
        """Test handling of invalid transaction formats"""
        # Test missing required field
        result = validate_transaction("TX-2023/INV-001|USER:john.doe|TYPE:INVALID|DESC:Missing amount field")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "Missing required field: amount")

        # Test invalid amount format
        result = validate_transaction("TX-2023/INV-002|USER:jane.smith|AMT:1234.5.6|TYPE:INVALID|DESC:Invalid number format")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "Invalid amount format")

        # Test malformed delimiters
        result = validate_transaction("TX-2023/INV-003||USER:bob||AMT:$100.00|TYPE:INVALID||DESC:Extra delimiters")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "Malformed transaction format")

if __name__ == '__main__':
    unittest.main()

