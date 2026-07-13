SELECT
  cm.company_category,
  COUNT(*) AS total_trips,
  SUM(t.trip_total) AS total_revenue
FROM
  `bigquery-public-data.chicago_taxi_trips.taxi_trips` AS t
INNER JOIN
  `test-to-sql-502205.text_to_sql.company_master` AS cm
ON
  t.company = cm.company_name
WHERE
  t.trip_start_timestamp >= TIMESTAMP('2024-01-01')
  AND t.trip_start_timestamp < TIMESTAMP('2025-01-01')
GROUP BY
  cm.company_category
ORDER BY
  total_revenue DESC;