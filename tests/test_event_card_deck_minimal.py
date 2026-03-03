import json
import tempfile
import unittest
from pathlib import Path

from src.game_objects.event_card import EventCardDeck


class EventCardDeckMinimalTests(unittest.TestCase):
    def _build_json_file(self) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="tk_evt_test_"))
        json_path = tmp_dir / "event_cards.json"
        payload = [
            {
                "id": "evt_1",
                "name": "事件一",
                "deck": "SHU",
                "target_country": "DRAWER",
                "description": "desc1",
                "effect_type": "pp",
                "effect_value": 1,
                "needs_target": False,
                "target_type": "",
            },
            {
                "id": "evt_2",
                "name": "事件二",
                "deck": "PUBLIC",
                "target_country": "DRAWER",
                "description": "desc2",
                "effect_type": "morale",
                "effect_value": -1,
                "needs_target": False,
                "target_type": "",
            },
        ]
        with json_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return json_path

    def test_draw_and_reshuffle_cycle(self) -> None:
        deck = EventCardDeck(self._build_json_file())

        c1 = deck.draw("SHU")
        c2 = deck.draw("SHU")
        self.assertIsNotNone(c1)
        self.assertIsNotNone(c2)
        self.assertEqual(deck.remaining(), 0)

        c3 = deck.draw("SHU")  # 触发弃牌回洗
        self.assertIsNotNone(c3)
        self.assertIn(c3.id, {"evt_1", "evt_2"})
        self.assertEqual(deck.remaining(), 1)

    def test_get_definition(self) -> None:
        deck = EventCardDeck(self._build_json_file())
        card = deck.get_definition("evt_1")
        self.assertIsNotNone(card)
        self.assertEqual(card.name, "事件一")


if __name__ == "__main__":
    unittest.main()
