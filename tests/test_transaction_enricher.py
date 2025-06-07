from decimal import Decimal

from statement_refinery.transaction_enricher import MerchantProfile, TransactionEnricher
from statement_refinery.txt_parser import Transaction


def test_merchant_profile_initialization():
    profile = MerchantProfile(name="TEST MERCHANT", category="DIVERSOS", last_seen="01/05")

    assert profile.name == "TEST MERCHANT"
    assert profile.category == "DIVERSOS"
    assert profile.last_seen == "01/05"
    assert profile.transaction_count == 0
    assert profile.total_amount == Decimal("0.00")
    assert profile.avg_amount == Decimal("0.00")
    assert not profile.recurring
    assert profile.typical_interval_days is None
    assert isinstance(profile.locations, set)
    assert isinstance(profile.currencies, set)


def test_normalize_merchant_name():
    enricher = TransactionEnricher()

    # Test prefix removal
    assert enricher._normalize_merchant_name("PAG*MERCHANT") == "MERCHANT"
    assert enricher._normalize_merchant_name("MP*STORE") == "STORE"
    assert enricher._normalize_merchant_name("*NETFLIX") == "NETFLIX"

    # Test installment suffix removal
    assert enricher._normalize_merchant_name("STORE 01/12") == "STORE"

    # Test location removal
    assert enricher._normalize_merchant_name("STORE .SAO PAULO") == "STORE"

    # Test case normalization
    assert enricher._normalize_merchant_name("Store") == "STORE"


def test_merchant_profile_updates():
    enricher = TransactionEnricher()

    # First transaction
    t1 = Transaction(
        post_date="01/05", description="NETFLIX", amount_brl=Decimal("45.90"), category="HOBBY"
    )
    enricher.update_merchant_profile(t1)

    profile = enricher.merchant_profiles["NETFLIX"]
    assert profile.transaction_count == 1
    assert profile.total_amount == Decimal("45.90")
    assert profile.avg_amount == Decimal("45.90")

    # Second transaction
    t2 = Transaction(
        post_date="01/06", description="NETFLIX", amount_brl=Decimal("45.90"), category="HOBBY"
    )
    enricher.update_merchant_profile(t2)

    profile = enricher.merchant_profiles["NETFLIX"]
    assert profile.transaction_count == 2
    assert profile.total_amount == Decimal("91.80")
    assert profile.avg_amount == Decimal("45.90")
    assert profile.typical_interval_days == 31  # One month interval


def test_enhanced_categorization():
    enricher = TransactionEnricher()

    # Test high priority categories
    t = Transaction(
        post_date="01/05", description="PAGAMENTO FATURA", amount_brl=Decimal("1000.00")
    )
    assert enricher.enhance_categorization(t) == "PAGAMENTO"

    # Test retail categories
    t = Transaction(post_date="01/05", description="FARMACIA SAO JOAO", amount_brl=Decimal("50.00"))
    assert enricher.enhance_categorization(t) == "FARMÁCIA"

    # Test dining categories
    t = Transaction(post_date="01/05", description="RESTAURANTE XYZ", amount_brl=Decimal("100.00"))
    assert enricher.enhance_categorization(t) == "RESTAURANTE"

    # Test international transactions
    t = Transaction(post_date="01/05", description="GITHUB.COM", amount_brl=Decimal("150.00"))
    assert enricher.enhance_categorization(t) == "TECNOLOGIA"

    # Test small adjustments
    t = Transaction(post_date="01/05", description="AJUSTE VALOR", amount_brl=Decimal("0.20"))
    assert enricher.enhance_categorization(t) == "AJUSTE"


def test_process_transactions():
    enricher = TransactionEnricher()

    transactions = [
        Transaction(post_date="01/05", description="NETFLIX", amount_brl=Decimal("45.90")),
        Transaction(post_date="01/06", description="NETFLIX", amount_brl=Decimal("45.90")),
        Transaction(
            post_date="15/05", description="FARMACIA SAO JOAO", amount_brl=Decimal("50.00")
        ),
        Transaction(
            post_date="15/06", description="FARMACIA SAO JOAO", amount_brl=Decimal("55.00")
        ),
        Transaction(post_date="01/05", description="GITHUB.COM", amount_brl=Decimal("150.00")),
    ]

    processed = enricher.process_transactions(transactions)

    # Check that all transactions were processed
    assert len(processed) == len(transactions)

    # Check that categories were assigned correctly
    assert processed[0].category == "HOBBY"  # Netflix
    assert processed[2].category == "FARMÁCIA"  # Farmácia
    assert processed[4].category == "TECNOLOGIA"  # GitHub

    # Check that merchant profiles were created
    assert len(enricher.merchant_profiles) == 3
    assert "NETFLIX" in enricher.merchant_profiles
    assert "FARMACIA SAO JOAO" in enricher.merchant_profiles
    assert "GITHUB.COM" in enricher.merchant_profiles
