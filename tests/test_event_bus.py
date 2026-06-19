import queue
import threading

from server.app.event_bus import EventBus


def test_event_bus_supports_cross_thread_publish_and_blocking_read():
    bus = EventBus()
    subscriber = bus.subscribe()

    def publish():
        bus.publish("task_changed", {"task_id": "task_1"})

    thread = threading.Thread(target=publish)
    thread.start()
    thread.join(timeout=1)

    event = subscriber.get(timeout=1)

    assert event["event"] == "task_changed"
    assert event["data"]["task_id"] == "task_1"


def test_event_bus_unsubscribe_stops_delivery():
    bus = EventBus()
    subscriber = bus.subscribe()
    bus.unsubscribe(subscriber)

    bus.publish("task_changed", {"task_id": "task_1"})

    try:
        subscriber.get(timeout=0.05)
    except queue.Empty:
        return
    raise AssertionError("unsubscribed queue should not receive events")
