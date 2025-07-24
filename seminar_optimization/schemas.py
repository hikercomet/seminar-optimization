# seminar_optimization/schemas.py
"""
セミナー割り当て問題の入力データ検証用JSONスキーマを定義します。
"""

SEMINARS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "セミナーの一意の識別子"},
            "capacity": {"type": "integer", "minimum": 1, "description": "セミナーの最大定員"},
            "magnification": {"type": "number", "minimum": 0, "description": "セミナーの倍率 (オプション)"}
        },
        "required": ["id", "capacity"],
        "additionalProperties": False # 定義されていないプロパティを許可しない
    },
    "description": "セミナーデータのリスト"
}

STUDENTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "学生の一意の識別子"},
            "preferences": {
                "type": "array",
                "items": {"type": "string", "description": "学生が希望するセミナーID"},
                "minItems": 1, # 最低1つの希望は必須とする
                "description": "学生の希望セミナーIDのリスト (優先順位順)"
            }
        },
        "required": ["id", "preferences"],
        "additionalProperties": False # 定義されていないプロパティを許可しない
    },
    "description": "学生データのリスト"
}

# 設定ファイル (config.json) のスキーマもここに定義することを検討できます。
# 例:
CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "num_seminars": {"type": "integer", "minimum": 1},
        "min_capacity": {"type": "integer", "minimum": 1},
        "max_capacity": {"type": "integer", "minimum": 1},
        "num_students": {"type": "integer", "minimum": 1},
        "min_preferences": {"type": "integer", "minimum": 1},
        "max_preferences": {"type": "integer", "minimum": 1},
        "preference_distribution": {"type": "string", "enum": ["random", "uniform", "biased"]},
        "random_seed": {"type": ["integer", "null"]},
        "optimization_strategy": {"type": "string", "enum": ["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive"]},
        "ga_population_size": {"type": "integer", "minimum": 1},
        "ga_generations": {"type": "integer", "minimum": 1},
        "ga_mutation_rate": {"type": "number", "minimum": 0, "maximum": 1},
        "ga_crossover_rate": {"type": "number", "minimum": 0, "maximum": 1},
        "ga_no_improvement_limit": {"type": "integer", "minimum": 1},
        "ilp_time_limit": {"type": "integer", "minimum": 1},
        "cp_time_limit": {"type": "integer", "minimum": 1},
        "max_workers": {"type": "integer", "minimum": 1},
        "multilevel_clusters": {"type": "integer", "minimum": 1},
        "greedy_ls_iterations": {"type": "integer", "minimum": 1},
        "local_search_iterations": {"type": "integer", "minimum": 1},
        "early_stop_no_improvement_limit": {"type": "integer", "minimum": 1},
        "initial_temperature": {"type": "number", "minimum": 0},
        "cooling_rate": {"type": "number", "minimum": 0, "maximum": 1},
        "generate_pdf_report": {"type": "boolean"},
        "generate_csv_report": {"type": "boolean"},
        "debug_mode": {"type": "boolean"},
        "log_enabled": {"type": "boolean"},
        "output_directory": {"type": "string"},
        "seminars_file": {"type": "string"},
        "students_file": {"type": "string"},
        "score_weights": {
            "type": "object",
            "properties": {
                "1st_choice": {"type": "number", "minimum": 0},
                "2nd_choice": {"type": "number", "minimum": 0},
                "3rd_choice": {"type": "number", "minimum": 0},
                "other_preference": {"type": "number", "minimum": 0}
            },
            "required": ["1st_choice", "2nd_choice", "3rd_choice", "other_preference"],
            "additionalProperties": False
        },
        "adaptive_history_size": {"type": "integer", "minimum": 1},
        "adaptive_exploration_epsilon": {"type": "number", "minimum": 0, "maximum": 1},
        "adaptive_learning_rate": {"type": "number", "minimum": 0, "maximum": 1},
        "adaptive_score_weight": {"type": "number", "minimum": 0, "maximum": 1},
        "adaptive_unassigned_weight": {"type": "number", "minimum": 0, "maximum": 1},
        "adaptive_time_weight": {"type": "number", "minimum": 0, "maximum": 1},
        "max_time_for_normalization": {"type": "number", "minimum": 1},
    },
    "required": [
        "num_seminars", "min_capacity", "max_capacity", "num_students",
        "min_preferences", "max_preferences", "preference_distribution",
        "optimization_strategy", "ga_population_size", "ga_generations",
        "ilp_time_limit", "cp_time_limit", "multilevel_clusters",
        "greedy_ls_iterations", "local_search_iterations",
        "early_stop_no_improvement_limit", "initial_temperature", "cooling_rate",
        "generate_pdf_report", "generate_csv_report", "debug_mode", "log_enabled",
        "output_directory", "seminars_file", "students_file", "score_weights",
        "ga_mutation_rate", "ga_crossover_rate", "ga_no_improvement_limit",
        "max_workers", "adaptive_history_size", "adaptive_exploration_epsilon",
        "adaptive_learning_rate", "adaptive_score_weight", "adaptive_unassigned_weight",
        "adaptive_time_weight", "max_time_for_normalization"
    ],
    "additionalProperties": False
}
