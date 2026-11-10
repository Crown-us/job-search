import unittest

from jobhunter import suspect

VIOVERA = {
    "source": "jobstreet",
    "company": "PT VIOVERA MARLI SEJAHTERA",
    "department": "Engineering | Civil/Structural Engineering",
    "description": "> Gaji di atas ekspektasi Persyaratan Tidak Disebutkan Tipe Pekerjaan Purna Waktu "
                   "PT Artha Demo Engineering Consultant adalah Perusahaan yang bergerak dalam jasa konsultasi.",
}


class SuspectTests(unittest.TestCase):
    def test_screenshot_case_is_hidden(self):
        why = suspect.verdict(VIOVERA, "fullstack")
        self.assertIn("Civil/Structural", why)
        self.assertIn("Artha Demo", why)
        self.assertIn("persyaratan kosong", why)
        self.assertIn("di atas ekspektasi", why)

    def test_one_flag_is_not_enough(self):
        row = {"source": "jobstreet", "company": "RS Sehat", "department": "Healthcare & Medical | Other",
               "description": "Kami rumah sakit, butuh IT Support untuk jaringan dan printer."}
        self.assertEqual(len(suspect.flags(row, "it_support")), 1)
        self.assertEqual(suspect.verdict(row, "it_support"), "")

    def test_money_ask_alone_hides(self):
        row = {"source": "kalibrr", "company": "PT Maju", "description": "Ada biaya pelatihan Rp 500.000."}
        self.assertNotEqual(suspect.verdict(row, "marketing"), "")

    def test_cv_is_not_a_company(self):
        row = {"source": "jobstreet", "company": "Kompas Gramedia",
               "description": "Kirim CV Anda dan CV Terbaru ke email kami."}
        self.assertEqual(suspect.flags(row, "video_editor"), [])

    def test_software_engineering_category_is_fine(self):
        row = {"source": "jobstreet", "company": "PT A", "department": "Engineering | Engineering - Software"}
        self.assertEqual(suspect.flags(row, "fullstack"), [])


if __name__ == "__main__":
    unittest.main()
