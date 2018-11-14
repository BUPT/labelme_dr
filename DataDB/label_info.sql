CREATE TABLE `label_info` (
  `id` int(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(63) DEFAULT NULL,
  `img_path` varchar(255) DEFAULT NULL,
  `json_path` varchar(255) DEFAULT NULL,
  `flags` text,
  `shapes` text,
  `retino_grade` int(255) DEFAULT NULL,
  `dme` int(255) DEFAULT NULL,
  `hard` varchar(255) DEFAULT NULL,
  `soft` varchar(255) DEFAULT NULL,
  `hemorrhage` varchar(255) DEFAULT NULL,
  `microaneurysms` varchar(255) DEFAULT NULL,
  `opticdisc` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=111121 DEFAULT CHARSET=utf8 ROW_FORMAT=DYNAMIC;