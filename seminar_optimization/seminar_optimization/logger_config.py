# seminar_optimization/logger_config.py
import logging
import os
from typing import Optional

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    アプリケーション全体のロギング設定を一元的に行います。
    この関数はアプリケーションの起動時に一度だけ呼び出されるべきです。

    Args:
        log_level (str): ロギングレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)。デフォルトは "INFO"。
        log_file (Optional[str]): ログを書き込むファイルパス。指定しない場合は標準出力にのみ出力。
    """
    # 既存のハンドラをクリアし、重複を防ぐ
    for handler in list(logging.root.handlers):
        logging.root.removeHandler(handler)
    
    # ルートロガーのレベルを設定
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"無効なログレベル: {log_level}")
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # ファイルハンドラを追加 (指定された場合)
    if log_file:
        try:
            # ログディレクトリが存在しない場合は作成
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logging.root.addHandler(file_handler)
            logging.getLogger(__name__).info(f"ログファイル '{log_file}' に出力します。")
        except Exception as e:
            logging.getLogger(__name__).error(f"ログファイル '{log_file}' の設定中にエラーが発生しました: {e}", exc_info=True)

    logging.getLogger(__name__).info(f"ロギングがレベル '{log_level}' で設定されました。")

# このモジュールが直接実行された場合のテスト用
if __name__ == "__main__":
    setup_logging(log_level="DEBUG", log_file="test_app.log")
    logger = logging.getLogger(__name__)
    logger.debug("これはデバッグメッセージです。")
    logger.info("これは情報メッセージです。")
    logger.warning("これは警告メッセージです。")
    logger.error("これはエラーメッセージです。")
    logger.critical("これは致命的なエラーメッセージです。")

    # 他のモジュールからロガーを取得する例
    another_logger = logging.getLogger("another_module")
    another_logger.info("別のモジュールからのメッセージです。")
