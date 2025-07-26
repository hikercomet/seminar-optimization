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
    """
    アプリケーションのGUI設定をgui_settings.iniファイルからロードおよび保存するクラス。
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.gui_settings_path = project_root / "gui_settings.ini"
        self.parser = configparser.ConfigParser()
        logger.debug(f"SettingsManager: 初期化。GUI設定パス: {self.gui_settings_path}")

    def load_gui_settings(self, app_instance: 'MainApplication') -> Dict[str, Any]:
        """
        gui_settings.iniからGUI設定をロードし、MainApplicationインスタンスの
        initial_*属性を更新するための辞書を返す。
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
                        if key == "score_weights":
                            loaded_settings[key] = json.loads(value)
                        elif key == "output_directory": # output_directoryはPathオブジェクトとしてロード
                            loaded_settings[key] = Path(value)
                        elif key.endswith("_path") or key.endswith("_directory"):
                            # その他のパスは文字列としてロード（例: pdf_font_path）
                            loaded_settings[key] = value
                        elif key in ["num_students", "min_capacity", "max_capacity", "random_seed",
                                     "ga_population_size", "ga_generations", "ga_no_improvement_limit",
                                     "ilp_time_limit", "cp_time_limit", "multilevel_clusters",
                                     "greedy_ls_iterations", "local_search_iterations", "no_improvement_limit",
                                     "num_preferences_to_consider"]:
                            loaded_settings[key] = int(value)
                        elif key in ["q_boost_probability", "ga_mutation_rate", "ga_crossover_rate",
                                     "initial_temperature", "cooling_rate", "early_stop_threshold"]:
                            loaded_settings[key] = float(value)
                        elif key in ["generate_pdf_report", "generate_csv_report", "debug_mode",
                                     "log_enabled", "save_intermediate"]:
                            loaded_settings[key] = self.parser.getboolean('GUI', key)
                        else:
                            loaded_settings[key] = value # その他の文字列値など
                logger.debug(f"SettingsManager: ロードされた設定: {loaded_settings}")
            except (configparser.Error, json.JSONDecodeError, ValueError) as e:
                logger.error(f"SettingsManager: gui_settings.iniの読み込み中にエラーが発生しました: {e}", exc_info=True)
                # エラーが発生した場合でも、app_instanceの初期値がそのまま使われるように、ここではloaded_settingsを更新しない
            except Exception as e:
                logger.error(f"SettingsManager: gui_settings.iniの読み込み中に予期せぬエラーが発生しました: {e}", exc_info=True)
                # エラーが発生した場合でも、app_instanceの初期値がそのまま使われるように、ここではloaded_settingsを更新しない
        else:
            logger.info("SettingsManager: gui_settings.iniが見つかりませんでした。デフォルト設定を使用します。")
        
        # ロードされた設定が不足している場合、app_instanceの初期値で補完
        # ただし、このメソッドはloaded_settingsを返すだけなので、app_instanceの属性更新は呼び出し元で行う
        return loaded_settings


    def save_gui_settings(self, settings: Dict[str, Any]):
        """
        現在のGUI設定をgui_settings.iniに保存する。
        settingsは、MainApplicationのinitial_属性のサフィックスをキーとする辞書であると想定。
        """
        logger.info("SettingsManager: GUI設定の保存を開始します。")
        if not self.parser.has_section('GUI'):
            self.parser.add_section('GUI')

        for key, value in settings.items():
            if isinstance(value, dict):
                # 辞書はJSON文字列として保存
                self.parser.set('GUI', key, json.dumps(value))
            elif isinstance(value, Path):
                # Pathオブジェクトは文字列に変換して保存
                self.parser.set('GUI', key, str(value))
            else:
                self.parser.set('GUI', key, str(value))

        try:
            with open(self.gui_settings_path, 'w', encoding='utf-8') as f:
                self.parser.write(f)
            logger.info("SettingsManager: GUI設定をgui_settings.iniに保存しました。")
        except Exception as e:
            logger.error(f"SettingsManager: gui_settings.iniの保存中にエラーが発生しました: {e}", exc_info=True)
