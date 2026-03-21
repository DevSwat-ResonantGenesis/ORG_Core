#!/usr/bin/env python3
"""
Stripe Product Setup Script

Creates the required products and prices in Stripe for ResonantGenesis.

Tiers (matching frontend signupLogic.ts):
- Developer: Free ($0) - no Stripe product needed
- Plus: $49/month, $490/year (2 months free)
- Enterprise: Custom pricing (contact sales)

Run: python3 scripts/setup_stripe_products.py

After running, copy the price IDs to your .env file.
"""

import os
import stripe
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

if not stripe.api_key:
    print("❌ ERROR: STRIPE_SECRET_KEY not found in environment")
    print("   Add it to .env file first")
    exit(1)

print("=" * 60)
print("STRIPE PRODUCT SETUP - ResonantGenesis")
print("=" * 60)
print()

# Check if products already exist
existing_products = stripe.Product.list(limit=100)
existing_names = {p.name: p for p in existing_products.data}

created_ids = {}

# ============================================
# PLUS PRODUCT ($49/month)
# ============================================
print("[PLUS PLAN]")

if "ResonantGenesis Plus" in existing_names:
    plus_product = existing_names["ResonantGenesis Plus"]
    print(f"  ✅ Product exists: {plus_product.id}")
else:
    plus_product = stripe.Product.create(
        name="ResonantGenesis Plus",
        description="50,000 credits/month, 20 agents, autonomous mode, agent teams, 5GB storage",
        metadata={
            "tier": "plus",
            "credits": "50000",
            "agents": "20",
        }
    )
    print(f"  ✅ Created product: {plus_product.id}")

created_ids["STRIPE_PRODUCT_PLUS"] = plus_product.id

# Check for existing prices
existing_prices = stripe.Price.list(product=plus_product.id, limit=10)
monthly_price = None
yearly_price = None

for price in existing_prices.data:
    if price.recurring and price.recurring.interval == "month":
        monthly_price = price
    elif price.recurring and price.recurring.interval == "year":
        yearly_price = price

# Create monthly price if not exists
if monthly_price:
    print(f"  ✅ Monthly price exists: {monthly_price.id} (${monthly_price.unit_amount/100}/mo)")
else:
    monthly_price = stripe.Price.create(
        product=plus_product.id,
        unit_amount=4900,  # $49.00
        currency="usd",
        recurring={"interval": "month"},
        metadata={"tier": "plus", "billing": "monthly"}
    )
    print(f"  ✅ Created monthly price: {monthly_price.id} ($49/mo)")

created_ids["STRIPE_PRICE_PLUS_MONTHLY"] = monthly_price.id

# Create yearly price if not exists
if yearly_price:
    print(f"  ✅ Yearly price exists: {yearly_price.id} (${yearly_price.unit_amount/100}/yr)")
else:
    yearly_price = stripe.Price.create(
        product=plus_product.id,
        unit_amount=49000,  # $490.00 (2 months free)
        currency="usd",
        recurring={"interval": "year"},
        metadata={"tier": "plus", "billing": "yearly"}
    )
    print(f"  ✅ Created yearly price: {yearly_price.id} ($490/yr - 2 months free)")

created_ids["STRIPE_PRICE_PLUS_YEARLY"] = yearly_price.id

# ============================================
# ENTERPRISE PRODUCT (Custom)
# ============================================
print("\n[ENTERPRISE PLAN]")

if "ResonantGenesis Enterprise" in existing_names:
    enterprise_product = existing_names["ResonantGenesis Enterprise"]
    print(f"  ✅ Product exists: {enterprise_product.id}")
else:
    enterprise_product = stripe.Product.create(
        name="ResonantGenesis Enterprise",
        description="Unlimited credits, unlimited agents, SSO, on-premise, dedicated support",
        metadata={
            "tier": "enterprise",
            "credits": "unlimited",
            "agents": "unlimited",
            "contact_sales": "true",
        }
    )
    print(f"  ✅ Created product: {enterprise_product.id}")

created_ids["STRIPE_PRODUCT_ENTERPRISE"] = enterprise_product.id
print("  ℹ️  Enterprise pricing is custom - handled via sales")

# ============================================
# CREDIT PACKS (One-time purchases)
# ============================================
print("\n[CREDIT PACKS]")

credit_packs = [
    {"name": "Starter Pack", "credits": 10000, "price": 1000, "id_key": "STARTER"},  # $10
    {"name": "Growth Pack", "credits": 50000, "price": 4000, "id_key": "GROWTH"},    # $40 (20% off)
    {"name": "Scale Pack", "credits": 200000, "price": 12000, "id_key": "SCALE"},    # $120 (40% off)
]

for pack in credit_packs:
    pack_name = f"ResonantGenesis {pack['name']}"
    
    if pack_name in existing_names:
        product = existing_names[pack_name]
        print(f"  ✅ {pack['name']} exists: {product.id}")
    else:
        product = stripe.Product.create(
            name=pack_name,
            description=f"{pack['credits']:,} Resonant Credits",
            metadata={
                "type": "credit_pack",
                "credits": str(pack['credits']),
            }
        )
        print(f"  ✅ Created {pack['name']}: {product.id}")
    
    # Check for existing one-time price
    existing_pack_prices = stripe.Price.list(product=product.id, limit=5)
    pack_price = None
    for p in existing_pack_prices.data:
        if not p.recurring:
            pack_price = p
            break
    
    if pack_price:
        print(f"      Price exists: {pack_price.id} (${pack_price.unit_amount/100})")
    else:
        pack_price = stripe.Price.create(
            product=product.id,
            unit_amount=pack['price'],
            currency="usd",
            metadata={"credits": str(pack['credits'])}
        )
        print(f"      Created price: {pack_price.id} (${pack['price']/100})")
    
    created_ids[f"STRIPE_PRICE_CREDITS_{pack['id_key']}"] = pack_price.id

# ============================================
# API PRODUCTS
# ============================================
print("\n[API PRODUCTS]")

api_products = [
    {
        "name": "State Physics API - Dev",
        "description": "Real-time anomaly detection for developers - 100k SU/month",
        "price": 4900,  # $49/month
        "id_key": "STATE_PHYSICS_DEV"
    },
    {
        "name": "State Physics API - Startup", 
        "description": "Advanced anomaly detection - 2M SU/month",
        "price": 29900,  # $299/month
        "id_key": "STATE_PHYSICS_STARTUP"
    },
    {
        "name": "Hash Sphere Memory API - Dev",
        "description": "Invariant-governed memory for AI - 100k MU/month",
        "price": 4900,  # $49/month
        "id_key": "HASH_SPHERE_DEV"
    },
    {
        "name": "Hash Sphere Memory API - Builder",
        "description": "Advanced memory system - 2M MU/month", 
        "price": 29900,  # $299/month
        "id_key": "HASH_SPHERE_STARTUP"
    }
]

for api in api_products:
    print(f"\n{api['name']}:")
    
    # Create product
    if api['name'] in existing_names:
        product = existing_names[api['name']]
        print(f"  ✅ Product exists: {product.id}")
    else:
        product = stripe.Product.create(
            name=api['name'],
            description=api['description'],
            metadata={
                "type": "api_subscription",
                "api_type": api['id_key'].split('_')[0].lower(),
                "tier": api['id_key'].split('_')[1].lower()
            }
        )
        print(f"  ✅ Created product: {product.id}")
    
    # Check for existing subscription price
    existing_prices = stripe.Price.list(product=product.id, limit=5)
    sub_price = None
    for p in existing_prices.data:
        if p.recurring and p.recurring.interval == 'month':
            sub_price = p
            break
    
    if sub_price:
        print(f"      Price exists: {sub_price.id} (${sub_price.unit_amount/100}/month)")
    else:
        sub_price = stripe.Price.create(
            product=product.id,
            unit_amount=api['price'],
            currency="usd",
            recurring={"interval": "month"},
            metadata={
                "api_type": api['id_key'].split('_')[0].lower(),
                "tier": api['id_key'].split('_')[1].lower()
            }
        )
        print(f"      Created price: {sub_price.id} (${api['price']/100}/month)")
    
    created_ids[f"STRIPE_PRICE_{api['id_key']}"] = sub_price.id

# ============================================
# OUTPUT ENV VARIABLES
# ============================================
print("\n" + "=" * 60)
print("ADD THESE TO YOUR .env FILE:")
print("=" * 60)
print()

for key, value in created_ids.items():
    print(f"{key}={value}")

print()
print("=" * 60)
print("✅ STRIPE SETUP COMPLETE")
print("=" * 60)
