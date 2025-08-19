// MongoDB 초기화 스크립트
db = db.getSiblingDB('travel_recsys');

// 사용자 생성
db.createUser({
  user: 'app_user',
  pwd: 'app_password',
  roles: [
    {
      role: 'readWrite',
      db: 'travel_recsys'
    }
  ]
});

// 컬렉션 생성 및 인덱스 설정
db.createCollection('user_features');
db.createCollection('user_profile');
db.createCollection('user_summary');
db.createCollection('user_recs');
db.createCollection('travel_info');

// 인덱스 생성
db.user_features.createIndex({ "ID": 1 }, { unique: true });
db.user_profile.createIndex({ "ID": 1 }, { unique: true });
db.user_summary.createIndex({ "ID": 1 }, { unique: true });
db.user_recs.createIndex({ "ID": 1 }, { unique: true });
db.travel_info.createIndex({ "product_code": 1 }, { unique: true });

// 샘플 데이터 (테스트용)
db.user_features.insertOne({
  "ID": "test_user",
  "Features": {
    "여행일정강도": "보통",
    "국내or해외": "해외",
    "산or바다": "바다",
    "랜드마크": "자연경관",
    "여행희망지역": "동남아시아",
    "싫어하는기후": "추위",
    "여행목적": "휴양",
    "숙소유형": "리조트",
    "여행예산": "중간"
  }
});

db.user_summary.insertOne({
  "ID": "test_user",
  "Summary": "따뜻한 동남아시아 해변에서 휴양을 즐기고 싶어하는 사용자입니다."
});

db.travel_info.insertMany([
  {
    "product_code": "BALI001",
    "title": "발리 힐튼 리조트 패키지",
    "price": "1,200,000원",
    "hashtags": ["발리", "리조트", "해변"],
    "features": ["수영장", "스파", "비치뷰"],
    "description": "발리 최고의 리조트에서 즐기는 럭셔리 휴양"
  },
  {
    "product_code": "PHUKET001", 
    "title": "푸켓 비치 리조트",
    "price": "950,000원",
    "hashtags": ["태국", "푸켓", "비치"],
    "features": ["해변", "마사지", "스노클링"],
    "description": "푸켓의 아름다운 해변에서 즐기는 휴양"
  }
]);

print('MongoDB 초기화 완료');
