CREATE TABLE IF NOT EXISTS reference_images (
  ref_id          CHAR(36) PRIMARY KEY,
  image_key       VARCHAR(512) NOT NULL,
  thumb_key       VARCHAR(512),
  source_type     ENUM('museum','self_render','stock') NOT NULL,
  license         VARCHAR(64) NOT NULL,
  attribution     VARCHAR(512),
  commercial_ok   TINYINT(1) NOT NULL DEFAULT 1,
  personas        JSON,
  tags            JSON,
  embedding_model VARCHAR(128) NOT NULL,
  width INT, height INT,
  render_params   JSON,
  ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX (source_type), INDEX (commercial_ok)
);

CREATE TABLE IF NOT EXISTS adoption_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  guide_id     CHAR(36) NOT NULL,
  reference_id CHAR(36) NOT NULL,
  persona      VARCHAR(32),
  source_type  VARCHAR(32),
  sub_problem  VARCHAR(48),
  event        ENUM('shown','clicked','saved','liked') NOT NULL,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX (reference_id), INDEX (guide_id), INDEX (sub_problem), INDEX (event)
);

CREATE TABLE IF NOT EXISTS miss_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  term VARCHAR(255) NOT NULL,
  context JSON,
  count INT DEFAULT 1,
  llm_suggestion VARCHAR(255),
  resolved TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
