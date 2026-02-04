"""
Test rent itemization to ensure no duplicates when applying to multiple blocks.

Tests that:
1. When rent items are created and applied to all periods, only ONE store item is created per rent item
2. The store item is associated with all blocks via StoreItemBlock
3. Teachers see one item with all blocks displayed
4. Students see items scoped to their block
"""
import pytest
from datetime import datetime
from decimal import Decimal
from app import create_app, db
from app.models import Admin, Student, RentSettings, RentItem, StoreItem, StoreItemBlock, TeacherBlock


@pytest.fixture
def app():
    """Create test application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def setup_teacher_and_blocks(app):
    """Create teacher with multiple blocks."""
    with app.app_context():
        # Create teacher
        teacher = Admin(
            username="testteacher",
            totp_secret="TESTSECRET123456"
        )
        db.session.add(teacher)
        db.session.flush()
        
        # Create rent settings for 3 blocks (A, B, C)
        blocks = ['A', 'B', 'C']
        rent_settings_list = []
        
        for block in blocks:
            rent_setting = RentSettings(
                teacher_id=teacher.id,
                block=block,
                is_enabled=True,
                rent_amount=Decimal('50.00'),
                frequency_type='monthly'
            )
            db.session.add(rent_setting)
            rent_settings_list.append(rent_setting)
        
        db.session.commit()
        
        return {
            'teacher': teacher,
            'blocks': blocks,
            'rent_settings': rent_settings_list
        }


def test_no_duplicate_store_items_when_applying_to_all_blocks(app, setup_teacher_and_blocks):
    """Test that applying rent items to all blocks creates only ONE store item per item."""
    with app.app_context():
        data = setup_teacher_and_blocks
        teacher = Admin.query.get(data['teacher'].id)
        blocks = data['blocks']
        
        # Create 2 rent items for each block (simulating "apply to all")
        item_names = ['Desk', 'Chair']
        
        for block in blocks:
            rent_setting = RentSettings.query.filter_by(
                teacher_id=teacher.id,
                block=block
            ).first()
            
            for name in item_names:
                rent_item = RentItem(
                    rent_setting_id=rent_setting.id,
                    name=name,
                    description=f"{name} rental",
                    is_available_in_store=True,
                    store_price=Decimal('10.00'),
                    purchase_duration='per_use'
                )
                db.session.add(rent_item)
        
        db.session.commit()
        
        # Now sync to store for each block (simulating the sync process)
        from app.routes.admin import _sync_rent_items_to_store
        
        for block in blocks:
            rent_setting = RentSettings.query.filter_by(
                teacher_id=teacher.id,
                block=block
            ).first()
            _sync_rent_items_to_store(rent_setting, teacher.id, block)
        
        # Check how many store items were created
        store_items = StoreItem.query.filter_by(teacher_id=teacher.id).all()
        
        # Should only have 2 store items (Desk and Chair), not 6 (2 × 3 blocks)
        assert len(store_items) == 2, f"Expected 2 store items, got {len(store_items)}"
        
        # Verify the items have the correct names
        item_names_found = sorted([item.name for item in store_items])
        assert item_names_found == ['Chair', 'Desk'], f"Expected ['Chair', 'Desk'], got {item_names_found}"
        
        # Verify each store item is associated with all 3 blocks
        for store_item in store_items:
            block_associations = StoreItemBlock.query.filter_by(
                store_item_id=store_item.id
            ).all()
            
            associated_blocks = sorted([assoc.block for assoc in block_associations])
            assert associated_blocks == blocks, \
                f"Item '{store_item.name}' should be associated with {blocks}, got {associated_blocks}"


def test_all_rent_items_linked_to_same_store_item(app, setup_teacher_and_blocks):
    """Test that all RentItems with same name are linked to the same StoreItem."""
    with app.app_context():
        data = setup_teacher_and_blocks
        teacher = Admin.query.get(data['teacher'].id)
        blocks = data['blocks']
        
        # Create rent item named "Desk" for each block
        for block in blocks:
            rent_setting = RentSettings.query.filter_by(
                teacher_id=teacher.id,
                block=block
            ).first()
            
            rent_item = RentItem(
                rent_setting_id=rent_setting.id,
                name='Desk',
                description='Desk rental',
                is_available_in_store=True,
                store_price=Decimal('10.00'),
                purchase_duration='per_use'
            )
            db.session.add(rent_item)
        
        db.session.commit()
        
        # Sync to store
        from app.routes.admin import _sync_rent_items_to_store
        
        for block in blocks:
            rent_setting = RentSettings.query.filter_by(
                teacher_id=teacher.id,
                block=block
            ).first()
            _sync_rent_items_to_store(rent_setting, teacher.id, block)
        
        # Get all rent items named "Desk"
        desk_rent_items = RentItem.query.join(
            RentSettings, RentItem.rent_setting_id == RentSettings.id
        ).filter(
            RentSettings.teacher_id == teacher.id,
            RentItem.name == 'Desk'
        ).all()
        
        assert len(desk_rent_items) == 3, "Should have 3 'Desk' rent items (one per block)"
        
        # All should have the same store_item_id
        store_item_ids = [item.store_item_id for item in desk_rent_items]
        unique_store_item_ids = set(store_item_ids)
        
        assert len(unique_store_item_ids) == 1, \
            f"All 'Desk' rent items should link to same store item, got IDs: {store_item_ids}"
        
        # Verify it's not None
        assert None not in store_item_ids, "All rent items should be linked to a store item"


def test_store_item_visible_to_correct_blocks(app, setup_teacher_and_blocks):
    """Test that store items are visible to the correct blocks only."""
    with app.app_context():
        data = setup_teacher_and_blocks
        teacher = Admin.query.get(data['teacher'].id)
        
        # Create rent item for blocks A and B only (not C)
        blocks_with_item = ['A', 'B']
        
        for block in blocks_with_item:
            rent_setting = RentSettings.query.filter_by(
                teacher_id=teacher.id,
                block=block
            ).first()
            
            rent_item = RentItem(
                rent_setting_id=rent_setting.id,
                name='Special Item',
                description='Only for A and B',
                is_available_in_store=True,
                store_price=Decimal('15.00'),
                purchase_duration='per_period'
            )
            db.session.add(rent_item)
        
        db.session.commit()
        
        # Sync to store
        from app.routes.admin import _sync_rent_items_to_store
        
        for block in blocks_with_item:
            rent_setting = RentSettings.query.filter_by(
                teacher_id=teacher.id,
                block=block
            ).first()
            _sync_rent_items_to_store(rent_setting, teacher.id, block)
        
        # Find the store item
        store_item = StoreItem.query.filter_by(
            teacher_id=teacher.id,
            name='Special Item'
        ).first()
        
        assert store_item is not None, "Store item should be created"
        
        # Check block associations
        block_associations = StoreItemBlock.query.filter_by(
            store_item_id=store_item.id
        ).all()
        
        associated_blocks = sorted([assoc.block for assoc in block_associations])
        assert associated_blocks == blocks_with_item, \
            f"Item should be associated with {blocks_with_item}, got {associated_blocks}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
