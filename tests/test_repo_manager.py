import pathlib
import unittest
from unittest.mock import MagicMock, patch

from src.repo_manager import (find_project_by_id, interactive_find_project_dir,
                              parse_project_dir)


class TestRepoManager(unittest.TestCase):

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.iterdir")
    def test_find_project_by_id_success(self, mock_iterdir, mock_exists):
        # Setup
        mock_exists.return_value = True

        # Mock Author Dir
        mock_author_dir = MagicMock()
        mock_author_dir.is_dir.return_value = True
        mock_author_dir.name = "Author1"

        # Mock Hidden Author Dir
        mock_hidden_author = MagicMock()
        mock_hidden_author.is_dir.return_value = True
        mock_hidden_author.name = ".HiddenAuthor"

        # Mock Project Dir
        mock_project_dir = MagicMock()
        mock_project_dir.is_dir.return_value = True
        mock_project_dir.name = "Title [ID123]"

        # Mock Hidden Project Dir
        mock_hidden_project = MagicMock()
        mock_hidden_project.is_dir.return_value = False
        mock_hidden_project.name = ".DS_Store"

        # IMPORTANT: author_dir is a Mock returned by the first iterdir call.
        # We must configure IT to return the project dirs when its iterdir() is called.
        mock_author_dir.iterdir.return_value = [mock_project_dir, mock_hidden_project]

        # We only need side_effect for the base_repo.iterdir() call
        mock_iterdir.return_value = [mock_author_dir, mock_hidden_author]

        # Test finding ID123
        result = find_project_by_id("ID123")
        self.assertEqual(result, mock_project_dir)

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.iterdir")
    def test_find_project_by_id_not_found(self, mock_iterdir, mock_exists):
        mock_exists.return_value = True
        mock_iterdir.return_value = []  # Empty repo

        result = find_project_by_id("NonExistentID")
        self.assertIsNone(result)

    def test_parse_project_dir_standard(self):
        # repo/Author/Title [ID]
        path = pathlib.Path("repo/Author Name/Job Title [ID123]")
        author, title, aid = parse_project_dir(path)

        self.assertEqual(author, "Author Name")
        self.assertEqual(title, "Job Title")
        self.assertEqual(aid, "ID123")

    def test_parse_project_dir_parens(self):
        # repo/Author/Title (Part 1) [ID]
        path = pathlib.Path("repo/Author/Book (Part 1) [ID123]")
        author, title, aid = parse_project_dir(path)

        self.assertEqual(title, "Book (Part 1)")
        self.assertEqual(aid, "ID123")

    def test_parse_project_dir_no_id(self):
        # repo/Author/Title
        path = pathlib.Path("repo/Author/Book Title")
        author, title, aid = parse_project_dir(path)

        self.assertEqual(title, "Book Title")
        self.assertEqual(aid, "Unknown")

    @patch("src.repo_manager.find_project_by_id")
    @patch("builtins.input")
    @patch("sys.exit")
    def test_interactive_find_success(self, mock_exit, mock_input, mock_find):
        # Flow:
        # 1. Ask ID -> 'ID123'
        # 2. Find returns Path
        # 3. Confirm -> 'y'
        # 4. Return Path

        mock_input.side_effect = ["ID123", "y"]
        mock_path = pathlib.Path("repo/Author/Title [ID123]")
        mock_find.return_value = mock_path

        result = interactive_find_project_dir()

        self.assertEqual(result, mock_path)
        mock_find.assert_called_with("ID123")

    @patch("src.repo_manager.find_project_by_id")
    @patch("builtins.input")
    @patch("sys.exit")
    def test_interactive_find_abort(self, mock_exit, mock_input, mock_find):
        # Flow:
        # 1. Ask ID -> 'ID123'
        # 2. Find returns Path
        # 3. Confirm -> 'n'
        # 4. Exit

        mock_input.side_effect = ["ID123", "n"]
        mock_path = pathlib.Path("repo/Author/Title [ID123]")
        mock_find.return_value = mock_path

        interactive_find_project_dir()

        mock_exit.assert_called_with(0)

    @patch("builtins.input", return_value="")
    def test_interactive_find_empty_input(self, mock_input):
        result = interactive_find_project_dir()
        self.assertIsNone(result)

    @patch("src.repo_manager.find_project_by_id")
    @patch("builtins.input")
    def test_interactive_find_not_found(self, mock_input, mock_find):
        mock_input.return_value = "MissingID"
        mock_find.return_value = None

        result = interactive_find_project_dir()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
