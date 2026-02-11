import pathlib
import sys
from typing import Optional, Tuple

from .utils import get_logger

logger = get_logger("RepoManager")


def find_project_by_id(audible_id: str) -> Optional[pathlib.Path]:
    """
    Scans repo/ for a directory matching the audible_id.
    Returns the Path object if found, else None.
    """
    base_repo = pathlib.Path("repo")
    if not base_repo.exists():
        return None
        
    # Pattern: */*[{audible_id}]
    # Glob treats [] as character selection, so we can't use it directly for literal brackets easily.
    # Instead, we'll iterate over all author folders and check project folders.
    
    candidates = []
    for author_dir in base_repo.iterdir():
        # print(f"DEBUG: Checking author_dir: {author_dir}, name={author_dir.name}, is_dir={author_dir.is_dir()}")
        if not author_dir.is_dir() or author_dir.name.startswith('.'):
            continue
            
        for project_dir in author_dir.iterdir():
            # print(f"DEBUG: Checking project_dir: {project_dir}, name={project_dir.name}, is_dir={project_dir.is_dir()}")
            if not project_dir.is_dir() or project_dir.name.startswith('.'):
                continue
                
            if f"[{audible_id}]" in project_dir.name:
                candidates.append(project_dir)
    
    if not candidates:
        return None
        
    if len(candidates) > 1:
        logger.warning(f"Multiple projects found for ID {audible_id}. Using the first one.")
        
    return candidates[0]


def parse_project_dir(project_dir: pathlib.Path) -> Tuple[str, str, str]:
    """
    Extracts (Author, Title, ID) from the project directory structure.
    Expects: repo/{Author}/{Title} [{ID}]
    """
    author = project_dir.parent.name
    dir_name = project_dir.name
    
    # ID is in brackets at end
    if "[" in dir_name and dir_name.endswith("]"):
        # rsplit to handle titles with brackets? 
        # safest is to find last '['
        last_bracket = dir_name.rfind("[")
        title = dir_name[:last_bracket].strip()
        audible_id = dir_name[last_bracket+1:-1].strip()
    else:
        title = dir_name
        audible_id = "Unknown"
        
    return author, title, audible_id


def interactive_find_project_dir() -> Optional[pathlib.Path]:
    """
    Prompts user for ID, searches repo, asks for confirmation.
    Returns the project directory Path if successful, None (or exit) otherwise.
    """
    print("Please enter the Audible ID of the book (e.g. B00XXXXXXX).")
    audible_id = input("Audible ID: ").strip()
    
    if not audible_id:
        logger.error("Audible ID is required.")
        return None
        
    found_dir = find_project_by_id(audible_id)
    
    if not found_dir:
        logger.error(f"No project found in 'repo/' matching ID: {audible_id}")
        return None
        
    author, title, aid = parse_project_dir(found_dir)
    
    print(f"\nFound existing project:")
    print(f"  Author: {author}")
    print(f"  Title:  {title}")
    print(f"  ID:     {aid}")
    print("-" * 60)
    
    confirm = input("Is this correct? [y/N]: ").strip().lower()
    if confirm != 'y':
        logger.info("Aborted by user.")
        sys.exit(0)
        
    return found_dir
