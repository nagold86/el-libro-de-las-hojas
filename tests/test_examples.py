"""The public example picker exposes only its curated original images."""

from __future__ import annotations


def test_catalogue_contains_ten_original_leaf_examples(client):
    response = client.get("/api/examples")

    assert response.status_code == 200
    examples = response.json()
    assert len(examples) == 10
    assert len({example["filename"] for example in examples}) == 10
    assert all(example["filename"].startswith("IMG_") for example in examples)
    assert all(example["image_url"].startswith("/api/examples/") for example in examples)


def test_example_images_are_served_but_unlisted_files_are_not(client):
    examples = client.get("/api/examples").json()
    image = client.get(examples[0]["image_url"])

    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert client.get("/api/examples/augmented_0_0.png").status_code == 404


def test_curated_example_can_be_analyzed_with_the_selected_method(client):
    example = client.get("/api/examples").json()[0]
    image = client.get(example["image_url"])

    analyzed = client.post(
        "/api/inspections",
        data={"method": "core2"},
        files={"file": (example["filename"], image.content, "image/png")},
    )

    assert analyzed.status_code == 201, analyzed.text
    assert analyzed.json()["trace"]["analysis_method"] == "core2"
