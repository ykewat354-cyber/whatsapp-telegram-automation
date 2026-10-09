#!/usr/bin/env python3
"""Entry point — WhatsApp Business Automation + Telegram Admin Panel."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()
