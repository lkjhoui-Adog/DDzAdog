from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATH = ROOT / "terrain" / "qgis" / "MichiganSurvival_TraverseCity_10km.qgs"


def add_vector(project, group, name, relative_path):
    path = ROOT / relative_path
    layer = QgsVectorLayer(str(path), name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Invalid vector layer: {path}")
    project.addMapLayer(layer, False)
    group.addLayer(layer)


def add_raster(project, group, name, relative_path):
    path = ROOT / relative_path
    layer = QgsRasterLayer(str(path), name)
    if not layer.isValid():
        raise RuntimeError(f"Invalid raster layer: {path}")
    project.addMapLayer(layer, False)
    group.addLayer(layer)


def main():
    QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 4.0.3\apps\qgis", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        project = QgsProject.instance()
        project.clear()
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:32616"))
        project.setTitle("MichiganSurvival Traverse City 10km")

        root = project.layerTreeRoot()
        export_group = root.addGroup("Terrain Builder Exports - UTM16N")
        vectors = export_group.addGroup("Projected Vectors")
        masks = export_group.addGroup("Masks")
        heights = export_group.addGroup("Heightmaps")

        add_vector(project, vectors, "Prototype Bounds UTM16N", "terrain/exports/utm16n/vectors/prototype_bounds_utm16n.geojson")
        add_vector(project, vectors, "Roads UTM16N", "terrain/exports/utm16n/vectors/roads_utm16n_clipped.geojson")
        add_vector(project, vectors, "Waterways UTM16N", "terrain/exports/utm16n/vectors/waterways_utm16n_clipped.geojson")
        add_vector(project, vectors, "Water Polygons UTM16N", "terrain/exports/utm16n/vectors/water_polygons_utm16n_clipped.geojson")
        add_vector(project, vectors, "Woods UTM16N", "terrain/exports/utm16n/vectors/woods_utm16n_clipped.geojson")
        add_vector(project, vectors, "Landuse UTM16N", "terrain/exports/utm16n/vectors/landuse_utm16n_clipped.geojson")

        add_raster(project, heights, "UTM16N Heightmap Float", "terrain/exports/utm16n/heightmap/michigan_survival_traverse_10km_utm16n_float.tif")

        for name in ["water", "woods", "roads", "farmland", "urban"]:
            add_raster(project, masks, f"{name.title()} Mask", f"terrain/exports/utm16n/masks/{name}_mask_4096_utm16n.tif")

        PROJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not project.write(str(PROJECT_PATH)):
            raise RuntimeError(f"Could not write QGIS project: {PROJECT_PATH}")
        print(f"Wrote {PROJECT_PATH}")
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    main()
