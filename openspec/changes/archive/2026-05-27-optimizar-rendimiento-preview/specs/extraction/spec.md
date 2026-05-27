# Delta for Extraction

## ADDED Requirements

### Requirement: Image Optimization

The pipeline SHOULD convert PDF pages to images at 150 DPI (down from 200 default).

The pipeline SHOULD save JPEG images at quality 60 (down from 85).

The pipeline SHOULD limit processed pages to the last 3 pages of each PDF.

Image optimization MUST NOT degrade extraction quality below an acceptable threshold.

#### Scenario: DPI reduction preserves readability

- GIVEN a scanned PDF invoice
- WHEN converted at 150 DPI
- THEN the Vision Agent MUST still extract all invoice fields correctly

#### Scenario: JPEG quality preserves readability

- GIVEN a PDF page converted to JPEG
- WHEN saved at quality 60
- THEN the Vision Agent MUST still extract all fields correctly

#### Scenario: Page limit for multi-page PDFs

- GIVEN a PDF with 10 pages
- WHEN the pipeline processes it
- THEN only the last 3 pages SHALL be converted to images
- AND pages 1-7 SHALL be skipped

#### Scenario: PDF with fewer than 3 pages

- GIVEN a PDF with 2 pages
- WHEN the pipeline processes it
- THEN all available pages SHALL be converted
- AND no error SHALL be raised
