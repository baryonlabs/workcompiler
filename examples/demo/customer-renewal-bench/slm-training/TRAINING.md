# Fleet evaluation — `write_pricing_cust_1001`

Held-out customers (never in the training split): CUST-2007, CUST-2010, CUST-2015, CUST-2017, CUST-2022, CUST-2030.
Dataset: 301 rows (recorded 1, fleet 300).

| model | pass | pass rate | avg tokens | avg latency |
| :-- | :-- | --: | --: | --: |
| qwen2.5:3b (raw) | 0/6 | 0% | 2,710 | 14.0 s |
| qwen2.5-3b + LoRA (fleet-trained, 200 iters) | 0/6 | 0% | 2,621 | 10.7 s |
| qwen2.5-3b + LoRA (fleet-trained) | 0/6 | 0% | 2,778 | 14.3 s |
| qwen2.5:7b (raw) | 0/6 | 0% | 2,754 | 29.9 s |
| qwen2.5-7b + LoRA (fleet-trained) | 0/6 | 0% | 5,325 | 88.9 s |
| qwen2.5-7b + QLoRA (4090-trained, 12 epochs) | 0/6 | 0% | 2,782 | 24.0 s |
| qwen2.5-7b + QLoRA (300 cases, 3 epochs) | 0/6 | 0% | 2,779 | 23.7 s |

## Per customer

### qwen2.5:3b (raw)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (json_values; cross_file_grounded; no_placeholder; proposal-CUST-2007.md: numbers not in JSON/context/derived: ['427256.1', '431698.8', '4502.4', '7454.7']) |
| CUST-2010 | FAIL (json_values; md_anchors; cross_file_grounded; no_placeholder; proposal-CUST-2010.md: numbers not in JSON/context/derived: ['1000', '2028', '2480', '3140']) |
| CUST-2015 | FAIL (json_values; md_anchors; cross_file_grounded; no_placeholder; proposal-CUST-2015.md: numbers not in JSON/context/derived: ['2028']) |
| CUST-2017 | FAIL (json_values; cross_file_grounded; no_placeholder; proposal-CUST-2017.md: numbers not in JSON/context/derived: ['120528']) |
| CUST-2022 | FAIL (json_values; md_anchors; no_placeholder) |
| CUST-2030 | FAIL (json_values; md_anchors; cross_file_grounded; no_placeholder; proposal-CUST-2030.md: numbers not in JSON/context/derived: ['2027']) |

### qwen2.5-3b + LoRA (fleet-trained, 200 iters)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (json_parses) |
| CUST-2010 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2010.json', 'build/renewal/proposal-CUST-2010.md']) |
| CUST-2015 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2015.json', 'build/renewal/proposal-CUST-2015.md']) |
| CUST-2017 | FAIL (file_set; json_parses; md_present; md_anchors; cross_file_grounded; files ['pricing_CUST-2017.json', 'proposal_CUST-2017.md'] != expected ['build/renewal/pricing-CUST-2017.json', 'build/renewal/proposal-CUST-2017.md']; proposal_CUST-2017.md: numbers not in JSON/context/derived: ['116796', '12560', '170844', '178477']) |
| CUST-2022 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2022.json', 'build/renewal/proposal-CUST-2022.md']) |
| CUST-2030 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2030.json', 'build/renewal/proposal-CUST-2030.md']) |

### qwen2.5-3b + LoRA (fleet-trained)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (json_values; cross_file_grounded; proposal-CUST-2007.md: numbers not in JSON/context/derived: ['1440', '2400', '3780', '45600']) |
| CUST-2010 | FAIL (json_values; cross_file_grounded; proposal-CUST-2010.md: numbers not in JSON/context/derived: ['1050', '212.5', '2125', '3930']) |
| CUST-2015 | FAIL (json_values) |
| CUST-2017 | FAIL (json_values; cross_file_grounded; proposal-CUST-2017.md: numbers not in JSON/context/derived: ['15648', '158400', '381.6', '4891.2']) |
| CUST-2022 | FAIL (json_values; cross_file_grounded; proposal-CUST-2022.md: numbers not in JSON/context/derived: ['123000', '12500', '150000', '325']) |
| CUST-2030 | FAIL (json_values; cross_file_grounded; proposal-CUST-2030.md: numbers not in JSON/context/derived: ['2100', '65500', '7500']) |

### qwen2.5:7b (raw)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (file_set; json_values; md_present; md_anchors; files ['build/renewal/pricing-CUST-2007.json'] != expected ['build/renewal/pricing-CUST-2007.json', 'build/renewal/proposal-CUST-2007.md']) |
| CUST-2010 | FAIL (file_set; json_values; md_present; md_anchors; files ['build/renewal/pricing-CUST-2010.json'] != expected ['build/renewal/pricing-CUST-2010.json', 'build/renewal/proposal-CUST-2010.md']) |
| CUST-2015 | FAIL (file_set; json_values; md_present; md_anchors; files ['build/renewal/pricing-CUST-2015.json'] != expected ['build/renewal/pricing-CUST-2015.json', 'build/renewal/proposal-CUST-2015.md']) |
| CUST-2017 | FAIL (file_set; json_values; md_present; md_anchors; files ['build/renewal/pricing-CUST-2017.json'] != expected ['build/renewal/pricing-CUST-2017.json', 'build/renewal/proposal-CUST-2017.md']) |
| CUST-2022 | FAIL (file_set; json_values; md_present; md_anchors; files ['build/renewal/pricing-CUST-2022.json'] != expected ['build/renewal/pricing-CUST-2022.json', 'build/renewal/proposal-CUST-2022.md']) |
| CUST-2030 | FAIL (file_set; json_values; md_present; md_anchors; files ['build/renewal/pricing-CUST-2030.json'] != expected ['build/renewal/pricing-CUST-2030.json', 'build/renewal/proposal-CUST-2030.md']) |

### qwen2.5-7b + LoRA (fleet-trained)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2007.json', 'build/renewal/proposal-CUST-2007.md']) |
| CUST-2010 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2010.json', 'build/renewal/proposal-CUST-2010.md']) |
| CUST-2015 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2015.json', 'build/renewal/proposal-CUST-2015.md']) |
| CUST-2017 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2017.json', 'build/renewal/proposal-CUST-2017.md']) |
| CUST-2022 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2022.json', 'build/renewal/proposal-CUST-2022.md']) |
| CUST-2030 | FAIL (file_set; json_parses; md_present; md_anchors; param_customer_id; files [] != expected ['build/renewal/pricing-CUST-2030.json', 'build/renewal/proposal-CUST-2030.md']) |

### qwen2.5-7b + QLoRA (4090-trained, 12 epochs)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (json_values; cross_file_grounded; proposal-CUST-2007.md: numbers not in JSON/context/derived: ['1440', '2400']) |
| CUST-2010 | FAIL (json_values; cross_file_grounded; proposal-CUST-2010.md: numbers not in JSON/context/derived: ['1530', '2550']) |
| CUST-2015 | FAIL (json_values) |
| CUST-2017 | FAIL (json_values; cross_file_grounded; proposal-CUST-2017.md: numbers not in JSON/context/derived: ['11136', '133632', '15360', '4608']) |
| CUST-2022 | FAIL (json_values; cross_file_grounded; proposal-CUST-2022.md: numbers not in JSON/context/derived: ['14700', '4410']) |
| CUST-2030 | FAIL (json_values; cross_file_grounded; proposal-CUST-2030.md: numbers not in JSON/context/derived: ['2250', '7500']) |

### qwen2.5-7b + QLoRA (300 cases, 3 epochs)

| customer | gate |
| :-- | :-- |
| CUST-2007 | FAIL (json_values; cross_file_grounded; proposal-CUST-2007.md: numbers not in JSON/context/derived: ['1440', '2400']) |
| CUST-2010 | FAIL (json_values; cross_file_grounded; proposal-CUST-2010.md: numbers not in JSON/context/derived: ['1620', '2700']) |
| CUST-2015 | FAIL (json_values) |
| CUST-2017 | FAIL (json_values; cross_file_grounded; proposal-CUST-2017.md: numbers not in JSON/context/derived: ['15360', '4608']) |
| CUST-2022 | FAIL (json_values; cross_file_grounded; proposal-CUST-2022.md: numbers not in JSON/context/derived: ['22500']) |
| CUST-2030 | FAIL (json_values; cross_file_grounded; proposal-CUST-2030.md: numbers not in JSON/context/derived: ['2250', '7500']) |
