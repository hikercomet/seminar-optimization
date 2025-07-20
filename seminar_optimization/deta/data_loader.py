# seminar_optimization/data/data_loader.py

import json
import csv
import random
import os
from typing import List, Dict, Any, Tuple

class DataLoader:
    """
    セミナーと学生のデータを異なるソースから読み込む機能を提供するクラス。
    """
    def __init__(self):
        self.seminars: List[Dict[str, Any]] = []
        self.students: List[Dict[str, Any]] = []

    def load_from_json(self, seminars_filepath: str = 'data/seminars.json', students_filepath: str = 'data/students.json'):
        """
        JSONファイルからセミナーと学生のデータを読み込みます。

        Args:
            seminars_filepath (str): セミナーデータのJSONファイルのパス。
            students_filepath (str): 学生データのJSONファイルのパス。
        """
        try:
            with open(seminars_filepath, 'r', encoding='utf-8') as f:
                self.seminars = json.load(f)
            print(f"JSONからセミナーデータ '{seminars_filepath}' を読み込みました。")
        except FileNotFoundError:
            print(f"エラー: セミナーJSONファイル '{seminars_filepath}' が見つかりません。")
            self.seminars = []
        except json.JSONDecodeError:
            print(f"エラー: セミナーJSONファイル '{seminars_filepath}' の形式が不正です。")
            self.seminars = []
        except Exception as e:
            print(f"エラー: セミナーJSONファイルの読み込み中に予期せぬエラーが発生しました: {e}")
            self.seminars = []

        try:
            with open(students_filepath, 'r', encoding='utf-8') as f:
                self.students = json.load(f)
            print(f"JSONから学生データ '{students_filepath}' を読み込みました。")
        except FileNotFoundError:
            print(f"エラー: 学生JSONファイル '{students_filepath}' が見つかりません。")
            self.students = []
        except json.JSONDecodeError:
            print(f"エラー: 学生JSONファイル '{students_filepath}' の形式が不正です。")
            self.students = []
        except Exception as e:
            print(f"エラー: 学生JSONファイルの読み込み中に予期せぬエラーが発生しました: {e}")
            self.students = []

    def load_from_csv(self, seminars_filepath: str = None, students_filepath: str = None):
        """
        CSVファイルからセミナーと学生のデータを読み込みます。
        セミナーCSVヘッダーの例: id,name,capacity
        学生CSVヘッダーの例: id,name,preferences (preferencesはカンマ区切り)

        Args:
            seminars_filepath (str, optional): セミナーデータのCSVファイルのパス。Defaults to None.
            students_filepath (str, optional): 学生データのCSVファイルのパス。Defaults to None.
        """
        if seminars_filepath:
            try:
                with open(seminars_filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.seminars = []
                    for row in reader:
                        # 必須フィールドのチェック
                        if 'id' not in row or 'name' not in row or 'capacity' not in row:
                            print(f"警告: セミナーCSVのヘッダーが不足しています (ID: {row.get('id', '不明')})。この行はスキップされます。")
                            continue
                        try:
                            self.seminars.append({
                                'id': row['id'].strip(),
                                'name': row['name'].strip(),
                                'capacity': int(row['capacity'].strip())
                            })
                        except ValueError:
                            print(f"警告: セミナーCSVの容量が無効です (ID: {row.get('id', '不明')})。この行はスキップされます。")
                            continue
                print(f"CSVからセミナーデータ '{seminars_filepath}' を読み込みました。")
            except FileNotFoundError:
                print(f"エラー: セミナーCSVファイル '{seminars_filepath}' が見つかりません。")
                self.seminars = []
            except Exception as e:
                print(f"エラー: セミナーCSVファイルの読み込み中に予期せぬエラーが発生しました: {e}")
                self.seminars = []

        if students_filepath:
            try:
                with open(students_filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.students = []
                    for row in reader:
                        # 必須フィールドのチェック
                        if 'id' not in row or 'name' not in row or 'preferences' not in row:
                            print(f"警告: 学生CSVのヘッダーが不足しています (ID: {row.get('id', '不明')})。この行はスキップされます。")
                            continue
                        preferences = [pref.strip() for pref in row['preferences'].split(',') if pref.strip()]
                        self.students.append({
                            'id': row['id'].strip(),
                            'name': row['name'].strip(),
                            'preferences': preferences
                        })
                print(f"CSVから学生データ '{students_filepath}' を読み込みました。")
            except FileNotFoundError:
                print(f"エラー: 学生CSVファイル '{students_filepath}' が見つかりません。")
                self.students = []
            except Exception as e:
                print(f"エラー: 学生CSVファイルの読み込み中に予期せぬエラーが発生しました: {e}")
                self.students = []

    def load_from_code_input(self, seminars_data: List[Dict[str, Any]], students_data: List[Dict[str, Any]]):
        """
        コードで直接指定されたセミナーと学生のデータを読み込みます。

        Args:
            seminars_data (List[Dict[str, Any]]): セミナーデータのリスト。
            students_data (List[Dict[str, Any]]): 学生データのリスト。
        """
        self.seminars = seminars_data
        self.students = students_data
        print("コードからの直接入力でデータを読み込みました。")

    def generate_dummy_data(self, num_seminars: int = 5, num_students: int = 20):
        """
        ダミーのセミナーと学生のデータを生成します。

        Args:
            num_seminars (int): 生成するセミナーの数。Defaults to 5.
            num_students (int): 生成する学生の数。Defaults to 20.
        """
        self.seminars = []
        for i in range(num_seminars):
            self.seminars.append({
                'id': f'S{i+1:02d}',
                'name': f'セミナー{i+1}',
                'capacity': random.randint(5, 15) # ランダムな定員
            })

        self.students = []
        seminar_ids = [s['id'] for s in self.seminars]
        for i in range(num_students):
            # 各学生はランダムに3つのセミナーを希望します
            preferences = random.sample(seminar_ids, min(3, len(seminar_ids)))
            self.students.append({
                'id': f'ST{i+1:02d}',
                'name': f'学生{i+1}',
                'preferences': preferences
            })
        print(f"ダミーデータを生成しました: セミナー {num_seminars} 件、学生 {num_students} 件。")

    def get_data(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        読み込まれたセミナーと学生のデータを返します。

        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: セミナーと学生のデータのタプル。
        """
        return self.seminars, self.students

# --- DataLoaderクラスの動作確認のための使用例 ---
if __name__ == "__main__":
    # 実行時に一時ファイルを作成するためのディレクトリ
    temp_data_dir = "temp_data_for_dataloader_test"
    os.makedirs(temp_data_dir, exist_ok=True)

    # 1. JSONからの読み込み例
    print("--- JSONからの読み込み ---")
    # テスト用のJSONファイルを作成
    sample_seminars_json = [
        {"id": "S01", "name": "AI基礎", "capacity": 10},
        {"id": "S02", "name": "データサイエンス入門", "capacity": 12}
    ]
    sample_students_json = [
        {"id": "ST01", "name": "田中", "preferences": ["S01", "S02"]},
        {"id": "ST02", "name": "山田", "preferences": ["S02", "S01"]}
    ]
    json_seminars_path = os.path.join(temp_data_dir, 'seminars.json')
    json_students_path = os.path.join(temp_data_dir, 'students.json')
    with open(json_seminars_path, 'w', encoding='utf-8') as f:
        json.dump(sample_seminars_json, f, ensure_ascii=False, indent=4)
    with open(json_students_path, 'w', encoding='utf-8') as f:
        json.dump(sample_students_json, f, ensure_ascii=False, indent=4)

    loader_json = DataLoader()
    loader_json.load_from_json(json_seminars_path, json_students_path)
    seminars_json, students_json = loader_json.get_data()
    print("読み込まれたセミナー (JSON):", seminars_json)
    print("読み込まれた学生 (JSON):", students_json)
    print("-" * 30 + "\n")

    # 2. CSVからの読み込み例
    print("--- CSVからの読み込み ---")
    # テスト用のCSVファイルを作成
    csv_seminars_path = os.path.join(temp_data_dir, 'seminars.csv')
    csv_students_path = os.path.join(temp_data_dir, 'students.csv')
    sample_seminars_csv_content = "id,name,capacity\nS03,Web開発,8\nS04,モバイルアプリ開発,7"
    sample_students_csv_content = "id,name,preferences\nST03,佐藤,S03,S04\nST04,鈴木,S04,S03"
    with open(csv_seminars_path, 'w', encoding='utf-8') as f:
        f.write(sample_seminars_csv_content)
    with open(csv_students_path, 'w', encoding='utf-8') as f:
        f.write(sample_students_csv_content)

    loader_csv = DataLoader()
    loader_csv.load_from_csv(csv_seminars_path, csv_students_path)
    seminars_csv, students_csv = loader_csv.get_data()
    print("読み込まれたセミナー (CSV):", seminars_csv)
    print("読み込まれた学生 (CSV):", students_csv)
    print("-" * 30 + "\n")

    # 3. コードからの直接入力の例
    print("--- コードからの直接入力 ---")
    input_seminars = [
        {"id": "S05", "name": "デザイン思考", "capacity": 15}
    ]
    input_students = [
        {"id": "ST05", "name": "高橋", "preferences": ["S05"]}
    ]
    loader_input = DataLoader()
    loader_input.load_from_code_input(input_seminars, input_students)
    seminars_input, students_input = loader_input.get_data()
    print("読み込まれたセミナー (コード入力):", seminars_input)
    print("読み込まれた学生 (コード入力):", students_input)
    print("-" * 30 + "\n")

    # 4. コードでの生成の例
    print("--- コードでの生成 ---")
    loader_generated = DataLoader()
    loader_generated.generate_dummy_data(num_seminars=3, num_students=10)
    seminars_generated, students_generated = loader_generated.get_data()
    print("生成されたセミナー:", seminars_generated)
    print("生成された学生:", students_generated)
    print("-" * 30 + "\n")

    # テスト用の一時ファイルをクリーンアップ
    print("一時ファイルをクリーンアップ中...")
    for f_name in os.listdir(temp_data_dir):
        os.remove(os.path.join(temp_data_dir, f_name))
    os.rmdir(temp_data_dir)
    print("クリーンアップ完了。")
