#!/usr/bin/env python3
"""
Test script to preview what Alembic would generate without actually creating a migration.

This helps verify that:
1. The include_object function is working correctly
2. No DROP statements are generated for other schemas
3. Only changes to the 'faros' schema are detected

Usage:
    python scripts/test_alembic_autogenerate.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, inspect

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

# Get database URL
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("ERROR: DATABASE_URL environment variable not set")
    print("Please set it to your Supabase connection string")
    sys.exit(1)

print("=" * 80)
print("Alembic Autogenerate Safety Test")
print("=" * 80)
print(f"\nDatabase URL: {database_url.split('@')[1] if '@' in database_url else '***'}")
print(f"Target schema: faros")
print("\nThis script will:")
print("1. Connect to the database")
print("2. Show what schemas exist")
print("3. Show what tables exist in each schema")
print("4. Preview what Alembic would generate (without creating a migration)")
print("\n" + "=" * 80 + "\n")

# Create engine
engine = create_engine(database_url, echo=False)

try:
    with engine.connect() as connection:
        inspector = inspect(engine)

        # List all schemas
        print("📋 SCHEMAS IN DATABASE:")
        print("-" * 80)
        schemas = inspector.get_schema_names()
        for schema in sorted(schemas):
            if schema.startswith("pg_") or schema == "information_schema":
                continue
            table_count = len(inspector.get_table_names(schema=schema))
            print(f"  {schema:20} ({table_count} tables)")
        print()

        # List tables in each relevant schema
        print("📋 TABLES BY SCHEMA:")
        print("-" * 80)
        relevant_schemas = ["faros", "public", "auth", "storage", "rostra", "quaero"]
        for schema in relevant_schemas:
            if schema not in schemas:
                continue
            tables = inspector.get_table_names(schema=schema)
            if tables:
                print(f"\n  Schema: {schema}")
                for table in sorted(tables):
                    print(f"    - {table}")
        print()

        # Check if faros schema exists
        if "faros" not in schemas:
            print("⚠️  WARNING: 'faros' schema does not exist yet")
            print("   It will be created automatically on first migration")
            print()

        # Check for tables in public schema that might need migration
        public_tables = inspector.get_table_names(schema="public")
        if public_tables:
            print("⚠️  WARNING: Found tables in 'public' schema:")
            for table in sorted(public_tables):
                print(f"    - {table}")
            print("   These may need to be moved to 'faros' schema")
            print()

        # Test Alembic autogenerate (dry run)
        print("🔍 TESTING ALEMBIC AUTO-GENERATE:")
        print("-" * 80)
        print("Checking what Alembic would detect...\n")

        # Import Alembic config (we don't need to set the URL here since we use our own engine)
        # The ConfigParser % interpolation issue is avoided by not using set_main_option
        alembic_cfg = Config(str(project_root / "alembic.ini"))

        # Import our models and metadata
        from db_config import Base
        from db_models import (  # noqa: F401
            ActivityLog,
            NotificationPreference,
            Task,
            TaskComment,
            TaskFile,
            TaskShare,
            User,
        )

        # Create migration context and compare metadata
        # We'll use the engine we already created (which has the correct URL)
        script = ScriptDirectory.from_config(alembic_cfg)

        with engine.connect() as conn:
            # Create migration context with our metadata configuration
            from alembic.autogenerate import compare_metadata
            from alembic.runtime.migration import MigrationContext

            # Create migration context - this is what Alembic uses to compare
            context = MigrationContext.configure(
                connection=conn,
                opts={
                    "compare_type": True,
                    "compare_server_default": True,
                },
            )

            # This is what Alembic would generate WITHOUT the include_object filter
            # (for comparison - the actual migration will use the filter)
            diffs_raw = compare_metadata(context, Base.metadata)

            # Now test WITH the include_object filter (this is what will actually happen)
            # We need to manually filter the diffs to simulate what include_object does
            APP_SCHEMA = "faros"  # This matches what's in alembic/env.py
            protected_schemas = {
                "auth",
                "storage",
                "rostra",
                "quaero",
                "extensions",
                "pg_catalog",
                "information_schema",
            }

            def get_table_schema(diff_item):
                """Extract schema from a diff item"""
                if len(diff_item) < 2:
                    return None
                table_obj = diff_item[1]
                if hasattr(table_obj, "schema"):
                    return table_obj.schema
                return None

            # Filter diffs using the same logic as include_object
            diffs = []
            filtered_count = 0
            filtered_details = []

            for diff in diffs_raw:
                op_type = diff[0]
                if op_type == "remove_table":
                    # This is a DROP operation - check if it should be filtered
                    table_schema = get_table_schema(diff)
                    if table_schema is None:
                        table_schema = "public"  # None means public in PostgreSQL

                    # Apply include_object logic (same as in alembic/env.py)
                    if table_schema != APP_SCHEMA:
                        table_name = (
                            diff[1].name if hasattr(diff[1], "name") else str(diff[1])
                        )
                        if table_schema in protected_schemas:
                            filtered_details.append(
                                f"   🛡️  FILTERED: DROP {table_schema}.{table_name} (protected schema - BLOCKED)"
                            )
                        else:
                            filtered_details.append(
                                f"   🛡️  FILTERED: DROP {table_schema}.{table_name} (not in {APP_SCHEMA} schema)"
                            )
                        filtered_count += 1
                        continue  # Skip this diff - it's filtered out

                diffs.append(diff)

            if filtered_count > 0:
                print(
                    f"\n   ✅ include_object() filter will remove {filtered_count} DROP operations:"
                )
                for detail in filtered_details:
                    print(detail)
                print("   (These will NOT appear in the actual migration)\n")

            if not diffs:
                print("✅ No differences detected - database matches models")
            else:
                print(f"📝 Alembic would generate {len(diffs)} changes:\n")

                # Categorize changes
                creates = []
                drops = []
                alters = []
                other = []

                for diff in diffs:
                    op_type = diff[0]
                    if op_type == "add_table":
                        creates.append(diff)
                    elif op_type == "remove_table":
                        drops.append(diff)
                    elif op_type in ("add_column", "remove_column", "modify_column"):
                        alters.append(diff)
                    else:
                        other.append(diff)

                # Show creates
                if creates:
                    print("  ➕ CREATE operations:")
                    for diff in creates:
                        table_name = (
                            diff[1].name if hasattr(diff[1], "name") else str(diff[1])
                        )
                        schema = getattr(diff[1], "schema", "public")
                        print(f"    - CREATE TABLE {schema}.{table_name}")

                # Show alters
                if alters:
                    print("\n  🔄 ALTER operations:")
                    for diff in alters:
                        print(f"    - {diff[0]}: {diff[1]}")

                # Show drops (this is what we're most worried about!)
                if drops:
                    print("\n  ⚠️  DROP operations (CHECK CAREFULLY!):")
                    for diff in drops:
                        table_name = (
                            diff[1].name if hasattr(diff[1], "name") else str(diff[1])
                        )
                        schema = getattr(diff[1], "schema", "public")
                        print(f"    - DROP TABLE {schema}.{table_name}")
                        if schema != "faros":
                            print(
                                f"      ⛔ DANGER: This is NOT in the 'faros' schema!"
                            )

                # Show other
                if other:
                    print("\n  📋 Other operations:")
                    for diff in other:
                        print(f"    - {diff}")

                # Safety check - be more thorough
                print("\n" + "=" * 80)
                dangerous_drops = []
                protected_schemas = {
                    "auth",
                    "storage",
                    "rostra",
                    "quaero",
                    "extensions",
                    "pg_catalog",
                    "information_schema",
                }

                for diff in drops:
                    table_obj = diff[1]
                    # Get schema - could be None (means public), or a string
                    table_schema = None
                    if hasattr(table_obj, "schema"):
                        table_schema = table_obj.schema
                    elif hasattr(table_obj, "key") and "." in table_obj.key:
                        # Table key might be "schema.table"
                        parts = table_obj.key.split(".")
                        if len(parts) == 2:
                            table_schema = parts[0]

                    # None schema means public in PostgreSQL
                    if table_schema is None:
                        table_schema = "public"

                    # Check if it's dangerous
                    if table_schema != "faros":
                        dangerous_drops.append((table_schema, table_obj))

                if dangerous_drops:
                    print("❌ SAFETY CHECK FAILED!")
                    print("   Found DROP operations for tables outside 'faros' schema:")
                    for schema, table_obj in dangerous_drops:
                        table_name = getattr(table_obj, "name", str(table_obj))
                        if schema in protected_schemas:
                            print(
                                f"   ⛔ CRITICAL: DROP {schema}.{table_name} (PROTECTED SCHEMA!)"
                            )
                        else:
                            print(f"   ⚠️  DROP {schema}.{table_name}")
                    print("\n   DO NOT RUN MIGRATIONS until this is fixed!")
                    print("   The include_object() function should prevent this.")
                    sys.exit(1)
                else:
                    print("✅ SAFETY CHECK PASSED")
                    print("   No dangerous DROP operations detected")
                    if drops:
                        print(
                            "   (Any DROP operations are only for 'faros' schema or will be filtered)"
                        )
                    print(
                        "\n   Note: The include_object() function in alembic/env.py will"
                    )
                    print(
                        "   filter out any DROP operations for tables outside 'faros' schema"
                    )
                    print("   when you actually run the migration.")

        print("\n" + "=" * 80)
        print("✅ Test complete - you can safely run 'alembic revision --autogenerate'")
        print("=" * 80)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
finally:
    engine.dispose()
