import unittest

from backend.pipeline.reframe_vertical_tracked import (
    choose_active_face,
    center_at_frame,
    is_speech_time,
    smooth_centers,
    speech_intervals,
)


class ActiveSpeakerTrackingTests(unittest.TestCase):
    def test_speech_intervals_are_clipped_and_relative_to_clip(self) -> None:
        transcript = [
            {
                "start": 10,
                "end": 12,
                "words": [
                    {"start": 9.5, "end": 10.2},
                    {"start": 11.4, "end": 12.4},
                ],
            }
        ]

        intervals = speech_intervals(transcript, clip_start=10, clip_end=12)

        self.assertAlmostEqual(intervals[0][0], 0)
        self.assertAlmostEqual(intervals[0][1], 0.2)
        self.assertAlmostEqual(intervals[1][0], 1.4)
        self.assertAlmostEqual(intervals[1][1], 2)
        self.assertTrue(is_speech_time(0.1, intervals))
        self.assertFalse(is_speech_time(0.8, intervals))

    def test_prefers_face_with_mouth_motion_while_speech_is_active(self) -> None:
        listener = {"id": 1, "area": 1000, "mouth_motion": 0.01}
        speaker = {"id": 2, "area": 800, "mouth_motion": 0.08}

        selected = choose_active_face(
            [listener, speaker], speech_active=True, previous_face_id=1
        )

        self.assertEqual(selected, speaker)

    def test_holds_current_speaker_when_mouth_motion_is_ambiguous(self) -> None:
        listener = {"id": 1, "area": 1000, "mouth_motion": 0.03}
        speaker = {"id": 2, "area": 800, "mouth_motion": 0.032}

        selected = choose_active_face(
            [listener, speaker], speech_active=True, previous_face_id=1
        )

        self.assertEqual(selected, listener)

    def test_crop_position_moves_smoothly_and_interpolates_between_samples(self) -> None:
        anchors = smooth_centers([(0, 0.2), (10, 0.8)], alpha=0.5)

        self.assertEqual(anchors, [(0, 0.2), (10, 0.5)])
        self.assertAlmostEqual(center_at_frame(anchors, 5), 0.35)


if __name__ == "__main__":
    unittest.main()
