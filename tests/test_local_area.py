import unittest
from unittest import mock

from jobhunter import config, pipeline, score, site
from jobhunter.model import Job
from jobhunter.sources import jobstreet


class LocalAreaTests(unittest.TestCase):
    def test_site_groups_home_area(self):
        cases = {
            "Kota Kediri, East Java": ("kediri", "Kota Kediri"),
            "Kediri Regency, East Java": ("kediri", "Kediri Regency"),
            "Nganjuk, East Java": ("kediri", "Nganjuk"),
            "Malang, East Java": ("malang", "Malang"),
            "Batu, East Java": ("malang", "Batu"),
            "Kota Batu, Jawa Timur": ("malang", "Kota Batu"),
        }
        for location, expected in cases.items():
            self.assertEqual(site._place(location, False), expected, location)

    def test_batu_does_not_swallow_other_places(self):
        self.assertEqual(site._place("Batu Ampar, Batam, Riau Islands", False)[0], "batam")
        self.assertNotEqual(site._place("Batu Ceper, Tangerang, Banten", False)[0], "malang")
        self.assertNotEqual(site._place("Batubara, North Sumatra", False)[0], "malang")

    def test_bare_province_passes_location_filter(self):
        flt = config.filters()
        for location in ("East Java", "Batu, East Java", "Kota Kediri, East Java", "Pare, Jawa Timur"):
            job = Job(source="jobstreet", company="PT A", title="IT Support", url="https://e.x/1",
                      location=location)
            self.assertTrue(pipeline.passes_filters(job, flt), location)

    def test_home_area_counts_as_indonesia(self):
        for location in ("East Java", "Batu, East Java"):
            self.assertTrue(score._hits(location, score.ID_HINTS), location)

    def test_jobstreet_sends_where_only_when_given(self):
        resp = mock.Mock()
        resp.json.return_value = {"data": []}
        with mock.patch.object(jobstreet.SESSION, "get", return_value=resp) as get:
            jobstreet.fetch("it support", where="Kediri")
            self.assertEqual(get.call_args.kwargs["params"]["where"], "Kediri")
            jobstreet.fetch("it support")
            self.assertNotIn("where", get.call_args.kwargs["params"])


if __name__ == "__main__":
    unittest.main()
