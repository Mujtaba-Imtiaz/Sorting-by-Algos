import os
import random
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = None

from database import Database
from models import normalize_repository


def make_item(number, generator):
    return {"id": number, "name": f"repo{number}", "full_name": f"user{number % 50}/repo{number}",
            "owner": {"login": f"user{number % 50}"}, "description": generator.choice([None, "machine learning tool", "web app"]),
            "language": generator.choice(["Python", "Go", None, "Rust"]), "stargazers_count": generator.randint(0, 5000),
            "forks_count": generator.randint(0, 300), "open_issues_count": generator.randint(0, 50),
            "created_at": f"20{generator.randint(10, 24)}-0{generator.randint(1, 9)}-1{generator.randint(0, 9)}T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z", "license": generator.choice([None, {"name": "MIT License"}]),
            "default_branch": "main", "html_url": f"https://github.com/user/repo{number}",
            "archived": generator.random() < 0.1, "visibility": "public"}


@unittest.skipIf(QApplication is None, "PyQt6 is not installed")
class GuiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        path = Path(self.folder.name) / "gui.db"
        generator = random.Random(5)
        database = Database(path)
        database.save_repositories([normalize_repository(make_item(n, generator)) for n in range(1, 1201)])
        database.close()
        from ui.main_window import MainWindow
        self.window = MainWindow(path)

    def tearDown(self):
        self.window.close()
        self.folder.cleanup()

    def wait_for(self, condition, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.02)
        self.fail("timed out waiting for the GUI")

    def test_theme_can_be_switched_both_ways(self):
        from ui import theme
        start = theme.current_name
        self.window.toggle_theme()
        self.assertNotEqual(theme.current_name, start)
        self.assertEqual(theme.tokens["bg"], theme.THEMES[theme.current_name]["bg"])
        self.window.toggle_theme()
        self.assertEqual(theme.current_name, start)

    def test_startup_loads_records_and_dashboard(self):
        self.assertEqual(len(self.window.store.records), 1200)
        self.assertEqual(self.window.dashboard.card_values["total"].text(), "1,200")
        self.assertEqual(self.window.explorer.table.model.rowCount(), 100)  # one page only

    def test_explorer_filter_and_header_sorting(self):
        explorer = self.window.explorer
        row = explorer.filter_panel.add_row()
        row.column_combo.setCurrentIndex(row.column_combo.findData("language"))
        row.operator_combo.setCurrentIndex(row.operator_combo.findData("equals"))
        row.value_edit.setText("python")
        explorer.apply_filters()
        expected = [r for r in self.window.store.records if (r["language"] or "").lower() == "python"]
        self.assertEqual(len(explorer.displayed_records), len(expected))
        explorer.on_sort_requested("stars")
        stars = [r["stars"] for r in explorer.displayed_records]
        self.assertEqual(stars, sorted(stars))
        explorer.on_sort_requested("stars")
        stars = [r["stars"] for r in explorer.displayed_records]
        self.assertEqual(stars, sorted(stars, reverse=True))
        row.value_edit.setText("")
        explorer.apply_filters()
        self.assertIn("value", explorer.filter_panel.error_label.text().lower())
        self.assertEqual(len(self.window.store.records), 1200)

    def test_sorting_lab_single_run_scope_and_apply(self):
        sorting, explorer = self.window.sorting, self.window.explorer
        row = explorer.filter_panel.add_row()
        row.column_combo.setCurrentIndex(row.column_combo.findData("stars"))
        row.operator_combo.setCurrentIndex(row.operator_combo.findData("greater_than"))
        row.value_edit.setText("4000")
        explorer.apply_filters()
        filtered_count = len(explorer.filtered_records)
        self.assertTrue(0 < filtered_count < 1200)

        sorting.scope_combo.setCurrentIndex(1)
        sorting.algorithm_combo.setCurrentIndex(sorting.algorithm_combo.findData("Merge Sort"))
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 1)
        self.assertEqual(sorting.results_table.item(0, 2).text(), f"{filtered_count:,}")
        self.assertEqual(sorting.results_table.item(0, 10).text(), "Yes")
        self.assertTrue(sorting.apply_button.isEnabled())
        sorting.apply_button.click()
        stars = [r["stars"] for r in explorer.displayed_records]
        self.assertEqual(len(stars), filtered_count)
        self.assertEqual(stars, sorted(stars, reverse=True))
        self.assertEqual(len(self.window.store.records), 1200)

        sorting.scope_combo.setCurrentIndex(0)
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.item(0, 2).text() == "1,200")
        sorting.apply_button.click()
        self.assertEqual(len(explorer.displayed_records), 1200)
        self.assertEqual(explorer.filter_panel.conditions(), [])

    def test_apply_button_needs_a_full_run_and_explains_why(self):
        sorting = self.window.sorting
        sorting.sample_box.setChecked(True)
        sorting.sample_spin.setValue(1000)  # 1000 of 1200 records
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 1)
        self.assertFalse(sorting.apply_button.isEnabled())
        self.assertIn("Untick", sorting.status_label.text())
        self.assertIn("sorted 1,000 records", sorting.summary_label.text())

        sorting.sample_box.setChecked(False)
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.item(0, 2).text() == "1,200")
        self.assertTrue(sorting.apply_button.isEnabled())

    def test_benchmark_all_with_two_level_sort(self):
        sorting = self.window.sorting
        sorting.levels_editor.rows[0].column_combo.setCurrentIndex(
            sorting.levels_editor.rows[0].column_combo.findData("stars"))
        sorting.levels_editor.add_level("forks", False)
        sorting.sample_box.setChecked(True)
        sorting.sample_spin.setValue(400)
        sorting.benchmark_button.click()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 11)
        self.assertIn("Fastest", sorting.summary_label.text())
        verified = [sorting.results_table.item(r, 10).text() for r in range(10)]
        self.assertEqual(verified, ["Yes"] * 10)
        self.assertEqual({sorting.results_table.item(r, 2).text() for r in range(10)}, {"400"})
        self.assertIn("Bogo Sort", sorting.results_table.item(10, 0).text())
        self.assertTrue(sorting.results_table.item(10, 11).text().startswith("Not available"))
        self.assertFalse(sorting.apply_button.isEnabled())

    def test_bogo_sort_single_run_on_big_data_is_refused_with_a_message_and_works_on_a_sample(self):
        from PyQt6.QtWidgets import QMessageBox
        sorting = self.window.sorting
        sorting.algorithm_combo.setCurrentIndex(sorting.algorithm_combo.findData("Bogo Sort"))
        shown = []
        original = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a, **k: shown.append(a[1]))
        try:
            sorting.run_single()
        finally:
            QMessageBox.information = original
        self.assertIsNone(sorting.thread)
        self.assertEqual(len(shown), 1)
        sorting.sample_box.setChecked(True)
        sorting.sample_spin.setValue(6)
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 1)
        self.assertEqual(sorting.results_table.item(0, 0).text(), "Bogo Sort")
        self.assertEqual(sorting.results_table.item(0, 10).text(), "Yes")

    def test_bucket_sort_single_run_from_the_gui(self):
        sorting, explorer = self.window.sorting, self.window.explorer
        sorting.algorithm_combo.setCurrentIndex(sorting.algorithm_combo.findData("Bucket Sort"))
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 1)
        self.assertEqual(sorting.results_table.item(0, 10).text(), "Yes")
        sorting.apply_button.click()
        stars = [r["stars"] for r in explorer.displayed_records]
        self.assertEqual(stars, sorted(stars, reverse=True))

    def test_radix_sort_single_run_from_the_gui(self):
        sorting, explorer = self.window.sorting, self.window.explorer
        sorting.algorithm_combo.setCurrentIndex(sorting.algorithm_combo.findData("Radix Sort"))
        sorting.run_single()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 1)
        self.assertEqual(sorting.results_table.item(0, 10).text(), "Yes")
        sorting.apply_button.click()
        stars = [r["stars"] for r in explorer.displayed_records]
        self.assertEqual(stars, sorted(stars, reverse=True))

    def test_text_column_disables_counting_sort(self):
        sorting = self.window.sorting
        row = sorting.levels_editor.rows[0]
        row.column_combo.setCurrentIndex(row.column_combo.findData("language"))
        index = sorting.algorithm_combo.findData("Counting Sort")
        self.assertFalse(sorting.algorithm_combo.model().item(index).isEnabled())
        sorting.sample_box.setChecked(True)
        sorting.sample_spin.setValue(300)
        sorting.benchmark_button.click()
        self.wait_for(lambda: sorting.thread is None and sorting.results_table.rowCount() == 11)
        notes = [sorting.results_table.item(r, 11).text() for r in range(11)]
        self.assertEqual(sum(note.startswith("Not available") for note in notes), 4)  # counting, radix, bucket, bogo

    def test_search_methods(self):
        search = self.window.search
        search.column_combo.setCurrentIndex(search.column_combo.findData("id"))
        search.operator_combo.setCurrentIndex(search.operator_combo.findData("equals"))
        search.value_edit.setText("777")
        search.method_combo.setCurrentIndex(search.method_combo.findData("binary"))
        search.run_search()  # records are stored sorted by id, so no prompt appears
        self.assertEqual([r["id"] for r in search.table.records], [777])
        self.assertIn("Binary search", search.stats_label.text())
        search.method_combo.setCurrentIndex(search.method_combo.findData("linear"))
        search.run_search()
        self.assertIn("1,200 comparisons", search.stats_label.text())
        search.value_edit.setText("abc")
        search.run_search()
        self.assertTrue(search.error_label.text())

    def test_binary_search_on_unsorted_column_asks_before_sorting(self):
        search = self.window.search
        search.column_combo.setCurrentIndex(search.column_combo.findData("stars"))
        search.operator_combo.setCurrentIndex(search.operator_combo.findData("greater_than"))
        search.value_edit.setText("4900")
        search.method_combo.setCurrentIndex(search.method_combo.findData("binary"))
        original = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        try:
            search.run_search()
            self.assertIn("cancelled", search.error_label.text())
            QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
            search.run_search()
        finally:
            QMessageBox.question = original
        expected = [r for r in self.window.store.records if r["stars"] is not None and r["stars"] > 4900]
        self.assertEqual(len(search.table.records), len(expected))

    def test_export_tab_counts_and_writes(self):
        export = self.window.export
        self.assertIn("1,200 repositories", export.info_label.text())
        with tempfile.TemporaryDirectory() as folder:
            from exporter import export_csv
            path = Path(folder) / "all.csv"
            export_csv(path, export.records())
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(lines) - 1, 1200)

    def test_collection_buttons_and_url_validation(self):
        collection = self.window.collection
        self.assertTrue(collection.start_button.isEnabled())
        self.assertFalse(collection.pause_button.isEnabled())
        self.assertFalse(collection.resume_button.isEnabled())
        self.assertFalse(collection.stop_button.isEnabled())
        collection.url_radio.setChecked(True)
        collection.url_edit.setText("https://example.com/not-github")
        original = QMessageBox.warning
        QMessageBox.warning = staticmethod(lambda *a, **k: None)
        try:
            collection.start()
        finally:
            QMessageBox.warning = original
        self.assertIsNone(collection.thread)
        self.assertIn("Only github.com", collection.log.toPlainText())


if __name__ == "__main__":
    unittest.main()
