"""Tests for action type classification."""

import pytest

from src.matching.action_type import classify_action_type


class TestPurchaseClassification:
    def test_buy(self):
        assert classify_action_type("Buy headphones on Amazon") == "purchase"

    def test_purchase(self):
        assert classify_action_type("Purchase a new laptop") == "purchase"

    def test_order(self):
        assert classify_action_type("Order pizza from Dominos") == "purchase"

    def test_add_to_cart(self):
        assert classify_action_type("Add to cart the blue shoes") == "purchase"

    def test_checkout(self):
        assert classify_action_type("Checkout with my saved card") == "purchase"

    def test_add_to_bag(self):
        assert classify_action_type("Add to bag the jacket") == "purchase"


class TestSearchClassification:
    def test_search(self):
        assert classify_action_type("Search for python tutorials") == "search"

    def test_find(self):
        assert classify_action_type("Find the best restaurants nearby") == "search"

    def test_look_up(self):
        assert classify_action_type("Look up the weather forecast") == "search"

    def test_look_for(self):
        assert classify_action_type("Look for cheap flights to NYC") == "search"

    def test_query(self):
        assert classify_action_type("Query the database for errors") == "search"


class TestFormFillClassification:
    def test_fill(self):
        assert classify_action_type("Fill out the contact form") == "form_fill"

    def test_submit(self):
        assert classify_action_type("Submit the application form") == "form_fill"

    def test_sign_up(self):
        assert classify_action_type("Sign up for a new account") == "form_fill"

    def test_register(self):
        assert classify_action_type("Register for the event") == "form_fill"

    def test_apply(self):
        assert classify_action_type("Apply for the job posting") == "form_fill"

    def test_contact_form(self):
        assert (
            classify_action_type("Fill in the contact form on example.com")
            == "form_fill"
        )


class TestNavigateClassification:
    def test_go_to(self):
        assert classify_action_type("Go to the settings page") == "navigate"

    def test_navigate(self):
        assert classify_action_type("Navigate to the dashboard") == "navigate"

    def test_open(self):
        assert classify_action_type("Open the admin panel") == "navigate"

    def test_visit(self):
        assert classify_action_type("Visit the homepage") == "navigate"

    def test_browse_to(self):
        assert classify_action_type("Browse to the products page") == "navigate"


class TestExtractClassification:
    def test_extract(self):
        assert classify_action_type("Extract prices from the table") == "extract"

    def test_scrape(self):
        assert classify_action_type("Scrape all product names") == "extract"

    def test_get_the(self):
        assert classify_action_type("Get the email addresses") == "extract"

    def test_copy(self):
        assert classify_action_type("Copy the shipping address") == "extract"

    def test_download(self):
        assert classify_action_type("Download the report PDF") == "extract"

    def test_grab(self):
        assert classify_action_type("Grab the phone numbers") == "extract"


class TestLoginClassification:
    def test_log_in(self):
        assert classify_action_type("Log in to my account") == "login"

    def test_login(self):
        assert classify_action_type("Login to the portal") == "login"

    def test_sign_in(self):
        assert classify_action_type("Sign in with Google") == "login"

    def test_authenticate(self):
        assert classify_action_type("Authenticate with SSO") == "login"


class TestEdgeCases:
    def test_no_match(self):
        assert classify_action_type("Do something random") is None

    def test_empty_string(self):
        assert classify_action_type("") is None

    def test_multiple_matches_picks_highest_score(self):
        # "buy" (purchase) + "search" + "find" (search has 2 hits)
        result = classify_action_type("Search and find something to buy")
        assert result == "search"

    def test_case_insensitive(self):
        assert classify_action_type("BUY something on AMAZON") == "purchase"

    def test_mixed_action_purchase_wins(self):
        # "buy" + "purchase" + "add to cart" = 3 purchase hits
        result = classify_action_type(
            "Buy and purchase items, add to cart immediately"
        )
        assert result == "purchase"
