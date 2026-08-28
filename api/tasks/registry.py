"""
AgentProbe -- task registry

Seven task templates. Each maps a TaskName to a natural-language
description that Claude uses to navigate the site.

Good task descriptions are:
  - Specific about the goal (not vague like "find info")
  - Clear about what "done" means
  - Neutral about how to get there (agent figures out the path)
"""

from ..models import TaskName

TASK_REGISTRY: dict[TaskName, dict] = {

    TaskName.pricing_discovery: {
        "description": (
            "Find and extract the pricing for this website's plans. "
            "You are done when you can clearly state at least one price (with currency and billing period) "
            "or confirm that pricing requires contacting sales. "
            "Note any friction: login walls, 'Contact Sales' blocks, or prices shown only as images."
        ),
        "typical_hops": 2,
        "weight": 1.5,  # Higher weight -- pricing is the most critical page for AI shopping agents
    },

    TaskName.contact_extraction: {
        "description": (
            "Find all available ways to contact this company: email, phone, chat widget, contact form. "
            "You are done when you have found at least one direct contact method or the contact page. "
            "Note if contact info is buried behind 3+ clicks or requires sign-in."
        ),
        "typical_hops": 1,
        "weight": 1.0,
    },

    TaskName.checkout_initiation: {
        "description": (
            "Add any product, plan, or service to a cart or initiate a purchase/subscription flow. "
            "You are done when you reach a checkout, payment, or order confirmation page. "
            "If this is a SaaS product, clicking 'Get started', 'Start free trial', or 'Buy now' counts. "
            "Note CAPTCHAs, mandatory account creation, or phone/address fields that block you."
        ),
        "typical_hops": 3,
        "weight": 2.0,  # Highest weight -- this is where agent revenue is lost
    },

    TaskName.demo_booking: {
        "description": (
            "Find and initiate a demo booking, sales call request, or free trial signup. "
            "You are done when you reach a scheduling page, a form requesting your name/email to book, "
            "or have successfully submitted a request. "
            "Note if Calendly or booking tools fail to load or require account creation."
        ),
        "typical_hops": 2,
        "weight": 1.2,
    },

    TaskName.policy_retrieval: {
        "description": (
            "Find the refund, return, or cancellation policy. "
            "You are done when you can extract the key policy terms: "
            "refund window, conditions, how to cancel. "
            "Note if the policy is behind login, in a PDF that requires download, or genuinely absent."
        ),
        "typical_hops": 2,
        "weight": 0.8,
    },

    TaskName.support_routing: {
        "description": (
            "Find how to submit a support ticket or get technical help. "
            "You are done when you reach a support ticket form, a chat widget, or a help center. "
            "Note if support requires account login, has no self-serve option, or routes only to sales."
        ),
        "typical_hops": 2,
        "weight": 1.0,
    },

    TaskName.api_discovery: {
        "description": (
            "Find the API or developer documentation for this product. "
            "You are done when you reach an API reference page, SDK docs, or a developer portal. "
            "Note if API docs require account creation, are behind a paywall, or simply do not exist."
        ),
        "typical_hops": 2,
        "weight": 0.7,
    },
}
