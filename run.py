# -*- coding: utf-8 -*-
"""启动脚本：9000 端口同时服务前后端"""
import os
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
sys.path.insert(0, os.getcwd())

import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=9000)
