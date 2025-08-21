
import time
from extractors.hianime import HianimeExtractor

if __name__ == "__main__":
    start = time.time()
    # Always run the One Piece brute-force extractor, output to ./output
    import argparse
    class Args(argparse.Namespace):
        def __init__(self):
            self.output_dir = "output"
            self.link = None
            self.filename = None
            self.server = None
            self.aria = False
            self.no_subtitles = False
    args = Args()
    extractor = HianimeExtractor(args)
    extractor.run()
    elapsed = time.time() - start
    print(f"Took {int(elapsed / 60)}:{int((elapsed % 60))} to finish")
