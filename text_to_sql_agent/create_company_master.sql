CREATE OR REPLACE TABLE
  `test-to-sql-502205.text_to_sql.company_master`
AS

WITH companies AS (

  SELECT DISTINCT
    company AS company_name

  FROM
    `bigquery-public-data.chicago_taxi_trips.taxi_trips`

  WHERE
    company IS NOT NULL

)

SELECT

  ROW_NUMBER() OVER (
    ORDER BY company_name
  ) AS company_id,

  company_name,

  CASE
    WHEN MOD(ABS(FARM_FINGERPRINT(company_name)), 3) = 0
      THEN 'STANDARD'

    WHEN MOD(ABS(FARM_FINGERPRINT(company_name)), 3) = 1
      THEN 'PREMIUM'

    ELSE 'ECONOMY'
  END AS company_category,

  CASE
    WHEN MOD(ABS(FARM_FINGERPRINT(company_name)), 2) = 0
      THEN 'STREET_HAIL'

    ELSE 'DISPATCH'
  END AS service_type

FROM companies;