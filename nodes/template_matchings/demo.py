from ..dll.vision_dll import edge_match, shape_context, chamfer_match, sad_match, ncc_match
import cv2
import numpy as np

tpl = cv2.imread('images/tpl.jpg')
tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
h_tpl, w_tpl = tpl_gray.shape

algorithms = [
    ('edge', lambda img: edge_match(img, tpl_gray,
        tpl_canny_low=50, tpl_canny_high=150,
        match_threshold=0.5, min_score=0.2,
        angle_start=-45, angle_end=45, angle_step=5, max_results=200)),
    ('shape', lambda img: shape_context(img, tpl_gray,
        sample_step=5, n_radial=4, n_angular=8,
        min_score=0.4, max_targets=10, max_results=200)),
    ('chamfer', lambda img: chamfer_match(img, tpl_gray,
        tpl_canny_low=50, tpl_canny_high=150,
        max_dist=30, max_results=200)),
    ('sad', lambda img: sad_match(img, tpl_gray,
        tpl_canny_low=50, tpl_canny_high=150,
        max_dist=0.4, max_results=200)),
    ('ncc', lambda img: ncc_match(img, tpl_gray,
        tpl_canny_low=50, tpl_canny_high=150,
        min_score=0.5, max_results=200)),
]

color = (0, 255, 0)
print("Running all algorithms...\n")

for algo_name, algo_fn in algorithms:
    panels = []

    for i in range(1, 5):
        src = cv2.imread(f'images/img{i}.jpg')
        src_gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        canvas = src.copy()

        results, ms = algo_fn(src_gray)
        for r in results[:30]:
            cx, cy, angle = r['x'], r['y'], r['angle']
            rad = np.radians(angle)
            cos_a, sin_a = np.cos(rad), np.sin(rad)

            corners = np.array([
                [-w_tpl / 2, -h_tpl / 2], [w_tpl / 2, -h_tpl / 2],
                [w_tpl / 2, h_tpl / 2], [-w_tpl / 2, h_tpl / 2]
            ])
            rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
            pts = (corners @ rot.T + [cx, cy]).astype(np.int32)

            cv2.polylines(canvas, [pts], True, color, 1)

        cv2.putText(canvas, f"img{i} | {len(results)} matches | {ms:.0f}ms",
                    (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        print(f"  img{i}: {len(results):3d} matches  {ms:.1f}ms")
        panels.append(canvas)

    h_max = max(p.shape[0] for p in panels)
    w_max = max(p.shape[1] for p in panels)
    panels = [cv2.resize(p, (w_max, h_max)) for p in panels]

    top = np.hstack([panels[0], panels[1]])
    bot = np.hstack([panels[2], panels[3]])
    grid = np.vstack([top, bot])

    print(f"\n>>> {algo_name} — press any key for next, ESC to quit")
    cv2.imshow(algo_name, grid)
    key = cv2.waitKey(0) & 0xff
    cv2.destroyWindow(algo_name)
    if key == 27:
        break

cv2.destroyAllWindows()
