#!/usr/bin/env python3
"""
Pattern Enhancement System - Generates new regex patterns based on failed parsing analysis.
Creates adaptive patterns to improve parsing success rate.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PatternEnhancer:
    """Analyzes failed patterns and generates new regex patterns."""
    
    def __init__(self, analysis_file: Path):
        with open(analysis_file) as f:
            self.analysis = json.load(f)
        
        self.new_patterns = []
        self.enhanced_patterns = {}
        
    def analyze_failed_patterns(self) -> List[Dict]:
        """Analyze the most common failed patterns and generate solutions."""
        discovered = self.analysis.get("discovered_patterns", [])
        solutions = []
        
        for pattern in discovered:
            structure = pattern["structure"]
            count = pattern["count"]
            examples = pattern["examples"]
            
            # Generate solutions based on pattern analysis
            if self._is_currency_conversion_pattern(structure, examples):
                solutions.append(self._create_currency_conversion_pattern(pattern))
            elif self._is_payment_summary_pattern(structure, examples):
                solutions.append(self._create_payment_summary_pattern(pattern))
            elif self._is_transaction_code_pattern(structure, examples):
                solutions.append(self._create_transaction_code_pattern(pattern))
            elif self._is_fee_info_pattern(structure, examples):
                solutions.append(self._create_fee_pattern(pattern))
            elif self._is_embedded_transaction_pattern(structure, examples):
                solutions.append(self._create_embedded_transaction_pattern(pattern))
        
        return solutions
    
    def _is_currency_conversion_pattern(self, structure: str, examples: List[str]) -> bool:
        """Check if this is a currency conversion line."""
        indicators = ["dólar", "conversão", "BRL", "USD", "EUR"]
        return any(indicator.lower() in " ".join(examples).lower() for indicator in indicators)
    
    def _is_payment_summary_pattern(self, structure: str, examples: List[str]) -> bool:
        """Check if this is a payment summary line."""
        indicators = ["pagamentos efetuados", "saldo financiado", "total desta fatura"]
        return any(indicator.lower() in " ".join(examples).lower() for indicator in indicators)
    
    def _is_transaction_code_pattern(self, structure: str, examples: List[str]) -> bool:
        """Check if this is a transaction code line."""
        return any(re.search(r'[A-Z]{2,3} - \d+', ex) for ex in examples)
    
    def _is_fee_info_pattern(self, structure: str, examples: List[str]) -> bool:
        """Check if this is a fee information line."""
        indicators = ["valor juros", "multa", "encargo", "tarifa"]
        return any(indicator.lower() in " ".join(examples).lower() for indicator in indicators)
    
    def _is_embedded_transaction_pattern(self, structure: str, examples: List[str]) -> bool:
        """Check if this contains embedded transaction data."""
        return any(re.search(r'\d{1,2}/\d{1,2}.*\d+,\d{2}', ex) for ex in examples)
    
    def _create_currency_conversion_pattern(self, pattern: Dict) -> Dict:
        """Create pattern for currency conversion lines."""
        # Pattern: "Dólar de Conversão R$ 5,71 Dólar de Conversão R$ 5,77"
        regex = r"(?i)Dólar\s+de\s+Conversão\s+R\$\s+(?P<rate1>\d+,\d{2})(?:\s+Dólar\s+de\s+Conversão\s+R\$\s+(?P<rate2>\d+,\d{2}))?"
        
        return {
            "name": "currency_conversion",
            "pattern": regex,
            "description": "Currency conversion rate information",
            "example": pattern["examples"][0],
            "count": pattern["count"],
            "action": "extract_fx_rate"
        }
    
    def _create_payment_summary_pattern(self, pattern: Dict) -> Dict:
        """Create pattern for payment summary lines."""
        # Pattern: "P Pagamentos efetuados - 16.744,62"
        regex = r"^(?P<type>[A-Z])\s+(?P<desc>[\w\s]+)\s+-\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})$"
        
        return {
            "name": "payment_summary",
            "pattern": regex,
            "description": "Payment summary lines with amounts",
            "example": pattern["examples"][0],
            "count": pattern["count"],
            "action": "parse_as_summary"
        }
    
    def _create_transaction_code_pattern(self, pattern: Dict) -> Dict:
        """Create pattern for transaction code lines."""
        # Pattern: "PC - 00 01290 VK045 03/05/2024 VKRPOF01 G4082 0622596"
        regex = r"^(?P<code>[A-Z]{2,3})\s+-\s+(?P<ref>\d+\s+\d+\s+[A-Z0-9]+)\s+(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<details>[\w\s]+)$"
        
        return {
            "name": "transaction_code",
            "pattern": regex,
            "description": "Transaction reference codes with dates",
            "example": pattern["examples"][0],
            "count": pattern["count"],
            "action": "parse_as_reference"
        }
    
    def _create_fee_pattern(self, pattern: Dict) -> Dict:
        """Create pattern for fee information lines."""
        # Pattern: "Valor juros 477,06"
        regex = r"^(?P<desc>(?i)(?:valor\s+)?(?:juros|multa|encargo|tarifa)[\w\s]*)\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})$"
        
        return {
            "name": "fee_information",
            "pattern": regex,
            "description": "Fee and interest information",
            "example": pattern["examples"][0],
            "count": pattern["count"],
            "action": "parse_as_fee"
        }
    
    def _create_embedded_transaction_pattern(self, pattern: Dict) -> Dict:
        """Create pattern for embedded transaction data."""
        # Pattern: Lines with date and amount but different structure
        regex = r"(?P<date>\d{1,2}/\d{1,2})(?:\s+(?P<desc1>[\w\s]+?))?\s+(?P<amount1>\d{1,3}(?:\.\d{3})*,\d{2})(?:\s+(?P<currency>[A-Z]{3}))?\s+(?P<amount2>\d{1,3}(?:\.\d{3})*,\d{2})"
        
        return {
            "name": "embedded_transaction",
            "pattern": regex,
            "description": "Embedded transaction with multiple amounts",
            "example": pattern["examples"][0],
            "count": pattern["count"],
            "action": "parse_as_transaction"
        }
    
    def generate_enhanced_parser(self) -> str:
        """Generate enhanced parser code with new patterns."""
        solutions = self.analyze_failed_patterns()
        
        # Sort by impact (count)
        solutions.sort(key=lambda x: x["count"], reverse=True)
        
        parser_code = '''
def parse_statement_line_enhanced(line: str, year: int | None = None) -> dict | None:
    """Enhanced parser with additional patterns for better coverage."""
    from typing import Final
    import re
    import hashlib
    from decimal import Decimal
    
    original_line = line
    line = line.strip()
    if not line:
        return None
    
    # Enhanced patterns (generated from failed line analysis)
'''
        
        for i, solution in enumerate(solutions[:10]):  # Top 10 patterns
            pattern_var = f"RE_ENHANCED_{solution['name'].upper()}"
            parser_code += f'''
    {pattern_var}: Final = re.compile(r"{solution['pattern']}")
'''
        
        parser_code += '''
    
    # Try enhanced patterns first
'''
        
        for solution in solutions[:10]:
            pattern_var = f"RE_ENHANCED_{solution['name'].upper()}"
            parser_code += f'''
    # {solution['description']} (covers {solution['count']} failed lines)
    m = {pattern_var}.match(line)
    if m:
        return _handle_{solution['action']}(m, original_line, year)
'''
        
        parser_code += '''
    
    # Fall back to original parsing logic
    return parse_statement_line_original(line, year)
'''
        
        # Generate handler functions
        for solution in solutions[:10]:
            parser_code += f'''

def _handle_{solution['action']}(m, original_line: str, year: int | None = None) -> dict:
    """Handle {solution['description']}."""
    # Custom logic for {solution['name']} pattern
    # Example line: {solution['example']}
    
    # Extract common fields
    card_last4 = "0000"  # Default since these may not have card info
    ledger_hash = hashlib.sha1(original_line.encode()).hexdigest()
    
    # Pattern-specific extraction logic would go here
    # This is a placeholder - each pattern needs custom implementation
    
    return {{
        "card_last4": card_last4,
        "post_date": "2024-01-01",  # Placeholder
        "desc_raw": original_line[:50],
        "amount_brl": Decimal("0.00"),  # Extract from pattern
        "installment_seq": 0,
        "installment_tot": 0,
        "fx_rate": Decimal("0.00"),
        "iof_brl": Decimal("0.00"),
        "category": "DIVERSOS",
        "merchant_city": "",
        "ledger_hash": ledger_hash,
        "prev_bill_amount": Decimal("0.00"),
        "interest_amount": Decimal("0.00"),
        "amount_orig": Decimal("0.00"),
        "currency_orig": "",
        "amount_usd": Decimal("0.00"),
    }}
'''
        
        return parser_code
    
    def generate_pattern_report(self) -> Dict:
        """Generate a comprehensive pattern enhancement report."""
        solutions = self.analyze_failed_patterns()
        total_covered = sum(s["count"] for s in solutions)
        total_failed = self.analysis["summary"]["total_failed_lines"]
        
        return {
            "enhancement_summary": {
                "new_patterns_generated": len(solutions),
                "lines_potentially_covered": total_covered,
                "current_failed_lines": total_failed,
                "potential_success_improvement": f"{(total_covered / total_failed) * 100:.1f}%"
            },
            "generated_patterns": solutions,
            "implementation_priority": sorted(solutions, key=lambda x: x["count"], reverse=True)[:5],
            "next_steps": [
                "Implement handler functions for each pattern type",
                "Add pattern validation tests",
                "Integrate with main parser in prioritized order",
                "Create golden CSV updates for improved parsing"
            ]
        }


def main():
    analysis_file = Path("diagnostics/comprehensive_analysis.json")
    if not analysis_file.exists():
        print(f"Analysis file {analysis_file} not found. Run comprehensive_analysis.py first.")
        return 1
    
    enhancer = PatternEnhancer(analysis_file)
    
    # Generate pattern report
    report = enhancer.generate_pattern_report()
    
    # Save enhancement report
    enhancement_file = Path("diagnostics/pattern_enhancement.json")
    with open(enhancement_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Generate enhanced parser code
    enhanced_code = enhancer.generate_enhanced_parser()
    
    # Save enhanced parser
    parser_file = Path("diagnostics/enhanced_parser.py")
    with open(parser_file, 'w') as f:
        f.write(enhanced_code)
    
    print("="*60)
    print("PATTERN ENHANCEMENT REPORT")
    print("="*60)
    print(f"New patterns generated: {report['enhancement_summary']['new_patterns_generated']}")
    print(f"Lines potentially covered: {report['enhancement_summary']['lines_potentially_covered']}")
    print(f"Potential success improvement: {report['enhancement_summary']['potential_success_improvement']}")
    
    print("\nTOP 5 IMPLEMENTATION PRIORITIES:")
    for i, pattern in enumerate(report['implementation_priority'][:5], 1):
        print(f"{i}. {pattern['name']} - covers {pattern['count']} lines")
        print(f"   Example: {pattern['example']}")
    
    print(f"\nEnhanced parser code saved to: {parser_file}")
    print(f"Enhancement report saved to: {enhancement_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
