import pytest
import inspect
from app.agent import chunk_and_embed, prepare_quiz, prepare_eval, prepare_planner

import ast

def test_node_input_types_not_strict_dict():
    """
    Test that prepare_quiz, prepare_eval, prepare_planner
    do not have a strict `dict` type hint for `node_input`.
    """
    with open('app/agent.py', 'r') as f:
        tree = ast.parse(f.read())
        
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ['prepare_quiz', 'prepare_eval', 'prepare_planner', 'chunk_and_embed']:
            for arg in node.args.args:
                if arg.arg == 'node_input':
                    if isinstance(arg.annotation, ast.Name) and arg.annotation.id == 'dict':
                        assert False, f"Function {node.name} has strict 'dict' type hint for node_input which causes validation errors."

