#!/bin/bash
echo "========================================"
echo "  PharmaPOS Pro - Starting..."
echo "========================================"
pip install flask flask-cors bcrypt pyjwt -q
python3 app.py
