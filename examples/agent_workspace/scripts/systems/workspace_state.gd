extends Node

var counter_events := 0
var visited_screens: Array[String] = []


func record_screen(screen: String) -> void:
	if not visited_screens.has(screen):
		visited_screens.append(screen)


func increment_counter() -> void:
	counter_events += 1


func summary() -> Dictionary:
	return {
		"counter_events": counter_events,
		"visited_screens": visited_screens.duplicate(),
	}
