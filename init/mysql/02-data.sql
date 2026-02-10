USE kokomi;

INSERT INTO region 
    (id, name) 
VALUES
    (1, 'asia'),
    (2, 'eu'),
    (3, 'na'),
    (4, 'ru'),
    (5, 'cn');

INSERT INTO platform 
    (id, name) 
VALUES
    (1, 'qq_bot'),
    (2, 'qq_group'),
    (3, 'qq_guild'),
    (4, 'discord');

INSERT INTO region_version
    (region_id, short_version, full_version, version_start)
VALUES
    (1, '14.11', '14.11.0.post2/ef08cd31b41e488c3b3669ef3624cd62d73f1d27', CURRENT_TIMESTAMP), 
    (2, '14.11', '14.11.0.post3/83a28b8913164eb612d022bd9c69c398de66bfb5', CURRENT_TIMESTAMP), 
    (3, '14.11', '14.11.0.post1/2f3e7195c1bb2050de4cb206814e6a11309a2f67', CURRENT_TIMESTAMP), 
    (4, '25.12', '25.12.0.post4/08ec98b7a1fea2baa7281561d48d5bc76a36c05b', CURRENT_TIMESTAMP), 
    (5, '14.11', '14.11.0.post4/de23d92ec3bde0ee2ba1cd5dabfee5d670bdef8e', CURRENT_TIMESTAMP);