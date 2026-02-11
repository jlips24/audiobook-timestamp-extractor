import unittest
from unittest.mock import MagicMock, patch, call
import sys

import pathlib
from src.main import main
from src.models import Chapter


class TestMainIntegration(unittest.TestCase):

    @patch('src.main.argparse.ArgumentParser.parse_args')
    @patch('src.main.os.path.exists')
    @patch('src.main.EpubParser')
    @patch('src.main.get_book_metadata')
    @patch('src.main.verify_chapters')
    @patch('src.main.AudioAnalyzer')
    @patch('src.main.save_results')
    def test_main_success_flow(
        self,
        mock_save_results,
        mock_analyzer_cls,
        mock_verify,
        mock_get_metadata,
        mock_parser_cls,
        mock_exists,
        mock_args
    ):
        """
        Verify that main() correctly orchestrates the flow.
        """
        # 1. Setup Arguments
        mock_args.return_value = MagicMock(
            epub="test.epub",
            audio="test.m4b",
            verbose=False,
            find_missing=False,
            sync_md_to_json=False,
            sync_json_to_md=False
        )
        # Files exist
        mock_exists.return_value = True

        # 2. Setup Parser
        mock_parser_instance = MagicMock()
        mock_parser_cls.return_value = mock_parser_instance

        # 3. Setup Metadata
        mock_get_metadata.return_value = ("Test Author", "Test Title", "12345")

        # 4. Setup Chapters
        raw_chapters = [
            Chapter(index=1, toc_title="C1", search_phrase="Ph1", status="PENDING")
        ]
        mock_parser_instance.parse.return_value = raw_chapters

        # 5. Setup Verification
        # User keeps the chapter
        mock_verify.return_value = raw_chapters

        # 6. Setup Audio Analyzer & Search
        mock_analyzer_instance = MagicMock()
        mock_analyzer_cls.return_value = mock_analyzer_instance
        mock_analyzer_instance.get_duration.return_value = 3600.0
        # find_chapter_linear returns True (Found)
        mock_analyzer_instance.find_chapter_linear.return_value = True
        # Simulate updating the chapter status (side effect of find_chapter_linear in real code,
        # here we assume the function calls it and sets status internally,
        # but in main we just check flow. We can assume find_chapter_linear returns bool.)

        # Run Main
        main()

        # Assertions
        mock_parser_cls.assert_called_with("test.epub")
        mock_get_metadata.assert_called_with(mock_parser_instance)

        # Verify call to analyzer
        mock_analyzer_cls.assert_called_with("test.m4b", model_size="medium")  # Check default

        # Verify find_chapter loop
        mock_analyzer_instance.find_chapter_linear.assert_called()
        args, _ = mock_analyzer_instance.find_chapter_linear.call_args
        # args[0] should be the chapter
        self.assertEqual(args[0].toc_title, "C1")

        # Verify Save
        mock_save_results.assert_called_with(raw_chapters, "Test Author", "Test Title", "12345")

    @patch('src.main.argparse.ArgumentParser.parse_args')
    @patch('src.main.os.path.exists')
    @patch('src.main.EpubParser')
    @patch('src.main.get_book_metadata')
    @patch('src.main.verify_chapters')  # Add verify mock
    @patch('src.main.sys.exit')
    @patch('builtins.input', return_value='')  # Keep safety patch
    def test_main_no_chapters(
        self,
        mock_input,
        mock_exit,
        mock_verify,
        mock_get_metadata,
        mock_parser_cls,
        mock_exists,
        mock_args
    ):
        """Test exit if no chapters found in EPUB."""
        mock_args.return_value = MagicMock(
            epub="test.epub", 
            audio="test.m4b", 
            verbose=False,
            find_missing=False,
            sync_md_to_json=False,
            sync_json_to_md=False
        )
        mock_exists.return_value = True

        mock_parser_instance = MagicMock()
        mock_parser_cls.return_value = mock_parser_instance
        # make sure parse returns empty list
        mock_parser_instance.parse.return_value = []

        # mock metadata to ensure we don't get stuck there
        mock_get_metadata.return_value = ("Auth", "Title", "ID")

        main()

        # Verify we tried to parse
        mock_parser_instance.parse.assert_called()

        # Verify exit called
        self.assertTrue(mock_exit.called, "sys.exit should have been called")
        # Check args loosely if needed, but strict is fine
        mock_exit.assert_called_with(1)

    @patch('src.main.argparse.ArgumentParser.parse_args')
    @patch('src.main.os.path.exists')
    @patch('src.main.EpubParser')
    @patch('src.main.get_book_metadata')
    @patch('src.main.verify_chapters')
    @patch('src.main.sys.exit')
    def test_main_all_chapters_ignored(
        self,
        mock_exit,
        mock_verify,
        mock_get_metadata,
        mock_parser_cls,
        mock_exists,
        mock_args
    ):
        """Test exit(0) if user ignores all chapters during verification."""
        mock_args.return_value = MagicMock(
            epub="test.epub",
            audio="test.m4b",
            verbose=False,
            find_missing=False,
            sync_md_to_json=False,
            sync_json_to_md=False
        )
        mock_exists.return_value = True

        mock_parser_instance = MagicMock()
        mock_parser_cls.return_value = mock_parser_instance
        # Parse returns chapters
        raw_chapters = [Chapter(index=1, toc_title="C1", search_phrase="Ph1", status="PENDING")]
        mock_parser_instance.parse.return_value = raw_chapters

        mock_get_metadata.return_value = ("Auth", "Title", "ID")

        # Verify returns empty list (all ignored)
        mock_verify.return_value = []

        main()

        # Should exit with 0 (success/clean exit)
        mock_exit.assert_called_with(0)


if __name__ == "__main__":
    unittest.main()

    @patch('src.main.run_find_missing_mode')
    @patch('src.main.argparse.ArgumentParser.parse_args')
    @patch('src.main.sys.exit')
    def test_main_route_to_find_missing(self, mock_exit, mock_args, mock_run_find):
        """Test routing to run_find_missing_mode."""
        mock_args.return_value = MagicMock(
            epub="test.epub",
            audio="test.m4b",
            verbose=False,
            find_missing=True,
            sync_md_to_json=False,
            sync_json_to_md=False
        )
        
        main()
        
        mock_run_find.assert_called_once()
        mock_exit.assert_called_with(0)

    @patch('src.main.run_sync_mode')
    @patch('src.main.argparse.ArgumentParser.parse_args')
    @patch('src.main.sys.exit')
    def test_main_route_to_sync(self, mock_exit, mock_args, mock_run_sync):
        """Test routing to run_sync_mode."""
        mock_args.return_value = MagicMock(
            epub=None, audio=None, # Optional for sync
            verbose=False,
            find_missing=False,
            sync_md_to_json=True,
            sync_json_to_md=False
        )
        
        main()
        
        mock_run_sync.assert_called_once()
        mock_exit.assert_called_with(0)

    @patch('src.main.interactive_find_setup')
    @patch('src.main.EpubParser')
    @patch('src.main.os.path.exists')
    def test_run_find_missing_mode(self, mock_exists, mock_parser_cls, mock_interactive):
        """Test run_find_missing_mode logic."""
        from src.main import run_find_missing_mode
        args = MagicMock(epub="test.epub", audio="test.m4b")
        mock_exists.return_value = True
        
        run_find_missing_mode(args)
        
        mock_parser_cls.assert_called_with("test.epub")
        mock_interactive.assert_called_with(mock_parser_cls.return_value, "test.m4b")

    @patch('src.main.sync_md_to_json')
    @patch('src.main.interactive_find_project_dir')
    def test_run_sync_mode_md_to_json(self, mock_interactive, mock_sync):
        """Test run_sync_mode for MD -> JSON."""
        from src.main import run_sync_mode
        args = MagicMock(sync_md_to_json=True, sync_json_to_md=False)
        
        mock_interactive.return_value = pathlib.Path("repo/Project")
        
        run_sync_mode(args)
        
        mock_interactive.assert_called_once()
        mock_sync.assert_called_with(pathlib.Path("repo/Project"))

    @patch('src.main.sync_json_to_md')
    @patch('src.main.interactive_find_project_dir')
    def test_run_sync_mode_json_to_md(self, mock_interactive, mock_sync):
        """Test run_sync_mode for JSON -> MD."""
        from src.main import run_sync_mode
        args = MagicMock(sync_md_to_json=False, sync_json_to_md=True)
        
        mock_interactive.return_value = pathlib.Path("repo/Project")
        
        run_sync_mode(args)
        
        mock_sync.assert_called_with(pathlib.Path("repo/Project"))
