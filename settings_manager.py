import configparser
import json
import logging
from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING

# 型ヒントの循環参照を避けるため
if TYPE_CHECKING:
    from main_app import MainApplication # MainApplicationクラスへの参照

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.gui_settings_path = project_root / "gui_settings.ini"
        self.parser = configparser.ConfigParser()

    def load_gui_settings(self, app_instance: 'MainApplication') -> Dict[str, Any]:
        """
        gui_settings.iniからGUI設定をロードし、MainApplicationインスタンスの
        initial_*属性を更新する。
        """
        logger.debug(f"SettingsManager: gui_settings.iniのロードを開始します: {self.gui_settings_path}")
        loaded_settings = {}

        if self.gui_settings_path.exists():
            try:
                self.parser.read(self.gui_settings_path, encoding='utf-8')
                logger.info(f"SettingsManager: gui_settings.iniをロードしました: {self.gui_settings_path}")
                
                if 'GUI' in self.parser:
                    for key, value in self.parser.items('GUI'):
                        # 各設定を適切な型に変換してロード
                        # MainApplicationのinitial_*属性に対応するキー名を想定
                        if key == 'seminars':
                            loaded_settings['initial_seminars_str'] = value
                        elif key == 'magnification':
                            try:
                                loaded_settings['initial_magnification'] = json.loads(value.replace("'", "\""))
                            except json.JSONDecodeError as e:
                                logger.warning(f"SettingsManager: magnification設定の解析に失敗しました: {value}, エラー: {e}。デフォルト値を使用します。")
                                loaded_settings['initial_magnification'] = app_instance.initial_magnification # アプリインスタンスのデフォルトを使用
                        elif key in ['num_students', 'min_size', 'max_size', 'num_preferences_to_consider',
                                      'num_patterns', 'max_workers', 'local_search_iterations', 'no_improvement_limit',
                                      'ga_population_size', 'ga_generations', 'ga_no_improvement_limit',
                                      'ilp_time_limit', 'cp_time_limit', 'multilevel_clusters',
                                      'max_adaptive_iterations', 'strategy_time_limit', 'adaptive_history_size',
                                      'greedy_ls_iterations', 'num_seminars', 'min_preferences', 'max_preferences',
                                      'random_seed']:
                            try:
                                loaded_settings[f'initial_{key}'] = int(value)
                            except ValueError:
                                logger.warning(f"SettingsManager: '{key}' の値が無効です: '{value}'。デフォルト値を使用します。")
                                loaded_settings[f'initial_{key}'] = getattr(app_instance, f'initial_{key}')
                        elif key in ['q_boost_probability', 'initial_temperature', 'cooling_rate',
                                      'preference_weights_1st', 'preference_weights_2nd', 'preference_weights_3rd',
                                      'preference_weights_other', 'early_stop_threshold', 'adaptive_exploration_epsilon',
                                      'adaptive_learning_rate', 'adaptive_score_weight', 'adaptive_unassigned_weight',
                                      'adaptive_time_weight', 'max_time_for_normalization']:
                            try:
                                loaded_settings[f'initial_{key}'] = float(value)
                            except ValueError:
                                logger.warning(f"SettingsManager: '{key}' の値が無効です: '{value}'。デフォルト値を使用します。")
                                loaded_settings[f'initial_{key}'] = getattr(app_instance, f'initial_{key}')
                        elif key in ['log_enabled', 'save_intermediate', 'generate_pdf_report', 'generate_csv_report', 'debug_mode']:
                            loaded_settings[f'initial_{key}'] = self.parser.getboolean('GUI', key)
                        elif key in ['data_source', 'theme', 'config_file_path', 'student_file_path',
                                      'optimization_strategy', 'seminars_file_path', 'students_file_path',
                                      'data_input_method', 'preference_distribution', 'output_directory']:
                            loaded_settings[f'initial_{key}'] = value
                        else:
                            logger.warning(f"SettingsManager: 未知のGUI設定キー: {key} = {value}")
                else:
                    logger.warning("SettingsManager: gui_settings.iniに[GUI]セクションが見つかりません。")

            except Exception as e:
                logger.error(f"SettingsManager: gui_settings.iniの読み込み中に予期せぬエラーが発生しました: {e}", exc_info=True)
                # エラーが発生した場合でも、app_instanceの初期値がそのまま使われるように、ここではloaded_settingsを更新しない
        else:
            logger.info("SettingsManager: gui_settings.iniが見つかりませんでした。デフォルト設定を使用します。")
        
        # ロードされた設定が不足している場合、app_instanceの初期値で補完
        for attr_name in [attr for attr in dir(app_instance) if attr.startswith('initial_')]:
            if attr_name not in loaded_settings:
                loaded_settings[attr_name] = getattr(app_instance, attr_name)

        return loaded_settings


    def save_gui_settings(self, settings: Dict[str, Any]):
        """
        現在のGUI設定をgui_settings.iniに保存する。
        """
        logger.info("SettingsManager: GUI設定の保存を開始します。")
        if not self.parser.has_section('GUI'):
            self.parser.add_section('GUI')

        for key, value in settings.items():
            if isinstance(value, dict):
                # 辞書はJSON文字列として保存
                self.parser.set('GUI', key, json.dumps(value))
            else:
                self.parser.set('GUI', key, str(value))

        try:
            with open(self.gui_settings_path, 'w', encoding='utf-8') as configfile:
                self.parser.write(configfile)
            logger.info(f"SettingsManager: GUI設定を '{self.gui_settings_path}' に保存しました。")
        except Exception as e:
            logger.error(f"SettingsManager: GUI設定の保存中にエラーが発生しました: {e}", exc_info=True)
            raise # 呼び出し元でエラーを処理できるように再スロー
