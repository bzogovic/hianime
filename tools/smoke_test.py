import os
import sys
import tempfile
import shutil

# Ensure project root is on sys.path so imports work when this script is run
# from the tools/ directory (sys.path[0] would otherwise be tools/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from extractors.hianime import HianimeExtractor
from argparse import Namespace

def test_basic_functions():
    args = Namespace()
    args.output_dir = "output"
    args.link = None
    args.filename = None
    args.server = None
    args.aria = False
    args.no_subtitles = False

    ext = HianimeExtractor(args)
    print("\nBasic function tests:")
    print("Created HianimeExtractor")
    print("get_anime():", ext.get_anime().name)
    print("get_anime_from_link():", ext.get_anime_from_link("https://hianime.to/watch/one-piece-100").name)
    print("extract_video_url() on example.com (should return None or fail gracefully):")
    print(ext.extract_video_url("https://example.com"))

def test_file_operations():
    print("\nFile operation tests:")
    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="hianime_test_")
    try:
        args = Namespace()
        args.output_dir = test_dir
        args.link = None
        args.filename = None
        args.server = None
        args.aria = False
        args.no_subtitles = False
        
        ext = HianimeExtractor(args)
        
        # Test downloading to output directory
        test_url = "https://example.com/test.mp4"  # This will fail, but should do so gracefully
        result = ext.yt_dlp_download(test_url, ext.HEADERS, os.path.join(test_dir, "test"))
        print(f"Download attempt (should fail gracefully): {result}")
        
        # Verify output directory was created
        one_piece_dir = os.path.join(test_dir, "one-piece")
        print(f"Output directory created: {os.path.exists(one_piece_dir)}")
        
    finally:
        # Clean up
        shutil.rmtree(test_dir, ignore_errors=True)
        print("Test directory cleaned up")

if __name__ == "__main__":
    print("Running smoke tests...")
    test_basic_functions()
    test_file_operations()
    print("\nSmoke tests completed.")
