class_name InventoryItemDefinition
extends Resource

@export var item_id: StringName
@export var display_name: String
@export_multiline var description: String
@export_range(1, 999, 1) var max_stack: int = 99
