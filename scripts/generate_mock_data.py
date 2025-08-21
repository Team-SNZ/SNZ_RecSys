#!/usr/bin/env python3
"""
MongoDB 모킹 데이터 생성 스크립트

기존 User_1000_str.csv와 final_travel.csv 데이터를 기반으로
사용자 정보에 이름, 성별, 나이(50세 이상) 정보를 추가하여 MongoDB에 삽입

Usage:
    python generate_mock_data.py
"""

import os
import sys
import pandas as pd
import random
from pymongo import MongoClient
from faker import Faker
import logging
from typing import Dict, List, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Faker 설정 (한국어)
fake = Faker('ko_KR')
Faker.seed(42)  # 재현 가능한 결과를 위한 시드 설정
random.seed(42)

class MockDataGenerator:
    """MongoDB 모킹 데이터 생성기"""
    
    def __init__(self, mongodb_uri: str, database_name: str = "travel_recsys"):
        """
        초기화
        
        Args:
            mongodb_uri: MongoDB 연결 URI
            database_name: 데이터베이스 이름
        """
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.client = None
        self.db = None
        
        # 컬렉션 참조
        self.col_features = None
        self.col_profile = None
        self.col_summary = None
        self.col_recs = None
        self.col_travels = None
        self.col_travels_url = None
        
        # 데이터 파일 경로
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.user_csv_path = os.path.join(self.data_dir, 'User_1000_str.csv')
        self.travel_csv_path = os.path.join(self.data_dir, 'final_travel.csv')
    
    def connect_mongodb(self):
        """MongoDB 연결"""
        try:
            self.client = MongoClient(self.mongodb_uri)
            self.db = self.client[self.database_name]
            
            # 컬렉션 참조 설정
            self.col_features = self.db["user_features"]
            self.col_profile = self.db["user_profile"]
            self.col_summary = self.db["user_summary"]
            self.col_recs = self.db["user_recs"]
            self.col_travels = self.db["travel_info"]
            self.col_travels_url = self.db["travel_url"]
            
            # 연결 테스트
            self.client.admin.command("ping")
            logger.info(f"MongoDB 연결 성공: {self.database_name}")
            
        except Exception as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            raise
    
    def close_connection(self):
        """MongoDB 연결 종료"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 연결 종료")
    
    def generate_user_profile(self) -> Dict[str, Any]:
        """
        사용자 프로필 생성 (이름, 성별, 나이 50세 이상)
        
        Returns:
            사용자 프로필 딕셔너리
        """
        gender = random.choice(['남성', '여성'])
        age = random.randint(50, 65)  # 50세 이상 75세 이하
        
        if gender == '남성':
            name = fake.name_male()
        else:
            name = fake.name_female()
        
        return {
            'name': name,
            'gender': gender,
            'age': age
        }
    
    def clear_existing_data(self):
        """기존 데이터 삭제"""
        try:
            collections_to_clear = [
                self.col_features,
                self.col_profile, 
                self.col_summary,
                self.col_recs
            ]
            
            for collection in collections_to_clear:
                result = collection.delete_many({})
                logger.info(f"{collection.name} 컬렉션에서 {result.deleted_count}개 문서 삭제")
                
        except Exception as e:
            logger.error(f"기존 데이터 삭제 실패: {e}")
            raise
    
    def load_user_data(self) -> pd.DataFrame:
        """사용자 CSV 데이터 로드"""
        try:
            if not os.path.exists(self.user_csv_path):
                raise FileNotFoundError(f"사용자 데이터 파일을 찾을 수 없습니다: {self.user_csv_path}")
            
            df = pd.read_csv(self.user_csv_path)
            logger.info(f"사용자 데이터 로드 완료: {len(df)}개 레코드")
            return df
            
        except Exception as e:
            logger.error(f"사용자 데이터 로드 실패: {e}")
            raise
    
    def load_travel_data(self) -> pd.DataFrame:
        """여행 CSV 데이터 로드"""
        try:
            if not os.path.exists(self.travel_csv_path):
                raise FileNotFoundError(f"여행 데이터 파일을 찾을 수 없습니다: {self.travel_csv_path}")
            
            df = pd.read_csv(self.travel_csv_path)
            logger.info(f"여행 데이터 로드 완료: {len(df)}개 레코드")
            return df
            
        except Exception as e:
            logger.error(f"여행 데이터 로드 실패: {e}")
            raise
    
    def insert_user_data(self, user_df: pd.DataFrame):
        """사용자 데이터를 MongoDB에 삽입"""
        try:
            inserted_count = 0
            
            for _, row in user_df.iterrows():
                user_id = row["ID"]
                
                # 사용자 프로필 생성 (이름, 성별, 나이)
                user_profile = self.generate_user_profile()
                
                # 1. user_features 컬렉션
                feature_cols = [col for col in user_df.columns 
                              if col not in ["ID", "Profile", "Summary", "Rec_People", "Rec_Travel"]]
                features_dict = {col: row[col] for col in feature_cols}
                
                # 사용자 프로필 정보 추가
                # features_dict.update(user_profile)
                
                self.col_features.insert_one({
                    "ID": user_id,
                    "name": user_profile["name"],
                    "gender": user_profile["gender"],
                    "age": user_profile["age"],
                    "Features": features_dict
                })
                
                # 2. user_summary 컬렉션
                summary_value = row['Summary'] if 'Summary' in user_df.columns and pd.notna(row['Summary']) else ""
                
                self.col_summary.insert_one({
                    "ID": user_id,
                    "Summary": summary_value
                })
                
                # 3. user_profile 컬렉션
                profile_value = row["Profile"] if "Profile" in user_df.columns and pd.notna(row["Profile"]) else ""
                
                self.col_profile.insert_one({
                    "ID": user_id,
                    "Profile": profile_value
                })
                
                # 4. user_recs 컬렉션
                recs_cols = [col for col in user_df.columns if col.startswith("Rec_")]
                recs_dict = {col: row[col] if pd.notna(row[col]) else "" for col in recs_cols}
                
                self.col_recs.insert_one({
                    "ID": user_id,
                    "Recs": recs_dict
                })
                
                inserted_count += 1
                
                if inserted_count % 100 == 0:
                    logger.info(f"사용자 데이터 {inserted_count}개 삽입 완료")
            
            logger.info(f"총 {inserted_count}개 사용자 데이터 삽입 완료")
            
        except Exception as e:
            logger.error(f"사용자 데이터 삽입 실패: {e}")
            raise
    
    def insert_travel_data(self, travel_df: pd.DataFrame):
        """여행 데이터를 MongoDB에 삽입"""
        try:
            # 기존 여행 데이터 삭제
            self.col_travels.delete_many({})
            self.col_travels_url.delete_many({})
            
            inserted_count = 0
            
            for _, row in travel_df.iterrows():
                # 1. travel_info 컬렉션
                travel_info = {
                    "product_code": row["product_code"],
                    "title": row["title"],
                    "description": row["description"],
                    "hashtags": row["hashtags"].split(",") if pd.notna(row["hashtags"]) else [],
                    "features": row["features"].split(",") if pd.notna(row["features"]) else [],
                    "price": row["price"] if pd.notna(row["price"]) else None
                }
                
                self.col_travels.insert_one(travel_info)
                
                # 2. travel_url 컬렉션
                travel_url = {
                    "product_code": row["product_code"],
                    "url": row["url"]
                }
                
                self.col_travels_url.insert_one(travel_url)
                
                inserted_count += 1
            
            logger.info(f"총 {inserted_count}개 여행 데이터 삽입 완료")
            
        except Exception as e:
            logger.error(f"여행 데이터 삽입 실패: {e}")
            raise
    
    def generate_mock_data(self, clear_existing: bool = True):
        """
        모킹 데이터 생성 메인 메서드
        
        Args:
            clear_existing: 기존 데이터 삭제 여부
        """
        try:
            logger.info("모킹 데이터 생성 시작")
            
            # MongoDB 연결
            self.connect_mongodb()
            
            # 기존 데이터 삭제 (옵션)
            if clear_existing:
                logger.info("기존 데이터 삭제 중...")
                self.clear_existing_data()
            
            # CSV 데이터 로드
            logger.info("CSV 데이터 로드 중...")
            user_df = self.load_user_data()
            travel_df = self.load_travel_data()
            
            # 사용자 데이터 삽입 (이름, 성별, 나이 추가)
            logger.info("사용자 데이터 삽입 중...")
            self.insert_user_data(user_df)
            
            # 여행 데이터 삽입
            logger.info("여행 데이터 삽입 중...")
            self.insert_travel_data(travel_df)
            
            logger.info("모킹 데이터 생성 완료!")
            
        except Exception as e:
            logger.error(f"모킹 데이터 생성 실패: {e}")
            raise
        finally:
            self.close_connection()
    
    def verify_data(self):
        """삽입된 데이터 검증"""
        try:
            self.connect_mongodb()
            
            collections = {
                "user_features": self.col_features,
                "user_profile": self.col_profile,
                "user_summary": self.col_summary,
                "user_recs": self.col_recs,
                "travel_info": self.col_travels,
                "travel_url": self.col_travels_url
            }
            
            logger.info("=== 데이터 검증 결과 ===")
            for name, collection in collections.items():
                count = collection.count_documents({})
                logger.info(f"{name}: {count}개 문서")
                
                # 샘플 데이터 확인
                if count > 0:
                    sample = collection.find_one()
                    if name == "user_features" and "Features" in sample:
                        features = sample["Features"]
                        if "name" in features and "gender" in features and "age" in features:
                            logger.info(f"  샘플 프로필: {features['name']} ({features['gender']}, {features['age']}세)")
            
        except Exception as e:
            logger.error(f"데이터 검증 실패: {e}")
        finally:
            self.close_connection()


def main():
    """메인 함수"""

    # Docker Compose 환경의 MongoDB에 연결하기 위한 설정
    # Infra/.env 파일의 환경 변수를 사용합니다.
    # 스크립트 실행 전 .env 파일을 로드해야 합니다. (e.g., `source ../Infra/.env`)
    db_user = os.getenv('CONTAINER_MONGODB_ROOT_USERNAME', 'admin')
    db_password = os.getenv('CONTAINER_MONGODB_ROOT_PASSWORD')
    db_host = os.getenv('CONTAINER_MONGODB_HOST', 'localhost')  # Docker-compose에서 포트 포워딩
    db_port = int(os.getenv('CONTAINER_MONGODB_PORT', 27017))
    db_name = os.getenv('CONTAINER_MONGODB_DATABASE', 'travel_recsys')

    if not db_password:
        logger.error("'CONTAINER_MONGODB_ROOT_PASSWORD' 환경 변수가 설정되지 않았습니다.")
        logger.error("Infra/.env 파일을 참고하여 환경 변수를 설정해주세요.")
        sys.exit(1)

    # MongoDB 연결 URI 생성 (인증 DB는 admin으로 가정)
    mongodb_uri = f"mongodb://{db_user}:{db_password}@{db_host}:{db_port}/?authSource=admin"

    logger.info(f"Connecting to local MongoDB container: {mongodb_uri}/")

    try:
        # 데이터베이스 이름은 compose.yml과 동일하게 'travel_recsys'를 사용
        generator = MockDataGenerator(mongodb_uri, database_name=db_name)

        # 모킹 데이터 생성
        generator.generate_mock_data(clear_existing=True)

        # 데이터 검증
        generator.verify_data()

    except Exception as e:
        logger.error(f"스크립트 실행 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
