import unittest
from app.engine import resolve_conflicts

def detection(name, box, confidence=.8):
    return {'class': name, 'box': box, 'confidence': confidence}

class ConflictTests(unittest.TestCase):
    def test_conflicting_labels_abstain(self):
        rows = resolve_conflicts([detection('helmet', [0,0,100,100]), detection('head', [5,5,100,100])])
        self.assertEqual([d['class'] for d in rows], ['uncertain'])
        self.assertEqual(len(rows[0]['alternatives']), 2)

    def test_nearby_separate_people_remain(self):
        rows = [detection('helmet', [0,0,100,100]), detection('head', [80,0,180,100])]
        self.assertEqual(resolve_conflicts(rows), rows)

    def test_person_box_does_not_conflict(self):
        rows = [detection('helmet', [0,0,100,100]), detection('person', [0,0,100,100])]
        self.assertEqual(resolve_conflicts(rows), rows)

    def test_reverse_order_is_also_uncertain(self):
        rows = resolve_conflicts([detection('head', [0,0,100,100]), detection('helmet', [5,5,100,100])])
        self.assertEqual([d['class'] for d in rows], ['uncertain'])

if __name__ == '__main__':
    unittest.main()
