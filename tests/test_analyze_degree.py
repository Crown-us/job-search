import unittest

from jobhunter import analyze

PAD = " Kami mencari kandidat yang teliti, komunikatif, dan mau belajar hal baru di tim kecil kami." * 2
PROFILE = {"pengalaman_total_bulan": 17, "skill": {"web": ["Laravel", "PHP"]}}


def fit(jd: str) -> dict:
    return analyze.heuristic_analysis({"description": jd + PAD, "score": 80}, PROFILE)


class DegreeRequirementTests(unittest.TestCase):
    def test_required(self):
        for jd in (
            "Pendidikan minimal S1 Teknik Informatika",
            "Bachelor's degree in Computer Science",
            "Lulusan sarjana komputer",
        ):
            self.assertEqual(analyze.degree_requirement(jd), "required", jd)

    def test_d3_mentioned_means_open(self):
        for jd in (
            "Pendidikan minimal D3/S1 Teknik Informatika",
            "Minimal D3 semua jurusan",
            "S1 Informatika. D3 dengan pengalaman 2 tahun dipertimbangkan.",
            "Diploma or Bachelor's degree in IT",
        ):
            self.assertEqual(analyze.degree_requirement(jd), "d3_ok", jd)

    def test_preferred(self):
        for jd in (
            "Diutamakan lulusan S1 Teknik Informatika",
            "S1 Teknik Informatika (diutamakan)",
            "Bachelor's degree in Computer Science preferred",
            "Bachelor's degree is a plus",
            "Bachelor's degree or equivalent practical experience",
            "Preferred: Bachelor's degree",
            "Gelar S1 menjadi nilai plus",
        ):
            self.assertEqual(analyze.degree_requirement(jd), "preferred", jd)

    def test_preference_about_something_else_stays_required(self):
        for jd in (
            "S1 Teknik Informatika, diutamakan berpengalaman Laravel",
            "Berpengalaman diutamakan, S1 Informatika",
            "Bachelor's degree in CS. Experience with AWS preferred.",
            "Pendidikan S1\nDiutamakan domisili Jakarta",
            "Bachelor's degree or above, marketing/communication related majors preferred",
            "Bachelor's degree in any major (Chinese Literature preferred)",
        ):
            self.assertEqual(analyze.degree_requirement(jd), "required", jd)

    def test_d3_the_chart_library_is_not_a_diploma(self):
        jd = "Bachelor's degree in Computer Science.\nExperience with data visualization (D3, Chart.js)"
        self.assertEqual(analyze.degree_requirement(jd), "required")
        jd = "Bachelor's degree in CS, a related field, or equivalent practical experience.\nD3.js a plus"
        self.assertEqual(analyze.degree_requirement(jd), "preferred")

    def test_one_hard_mention_wins_over_soft(self):
        jd = "Minimal S1 Informatika.\nS1 dari kampus ternama diutamakan."
        self.assertEqual(analyze.degree_requirement(jd), "required")

    def test_no_degree_and_high_school(self):
        self.assertEqual(analyze.degree_requirement("Menguasai Laravel dan MySQL"), "")
        self.assertEqual(analyze.degree_requirement("High school diploma required"), "")

    def test_penalty_scales_with_strictness(self):
        hard = fit("Pendidikan minimal S1 Teknik Informatika. Menguasai Laravel.")
        soft = fit("Diutamakan lulusan S1 Teknik Informatika. Menguasai Laravel.")
        open_ = fit("Pendidikan minimal D3/S1 Teknik Informatika. Menguasai Laravel.")
        self.assertEqual(soft["fit"] - hard["fit"], 7)
        self.assertEqual(open_["fit"] - soft["fit"], 3)
        self.assertIn(analyze.GAP_S1, hard["gaps"])
        self.assertIn(analyze.GAP_S1_SOFT, soft["gaps"])
        self.assertIn("D3 diterima/disebut eksplisit", open_["strengths"])
        self.assertFalse([g for g in open_["gaps"] if "S1" in g])


if __name__ == "__main__":
    unittest.main()
