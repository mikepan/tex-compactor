html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Optimization Report</title>
    <style>
        html{{
            scrollbar-gutter: stable;
        }}
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #eee;
            color: #333;
        }}
        h1, .total-savings {{
            text-align: center;
            color: #333;
        }}
        table {{
            width: 80%;
            border-collapse: collapse;
            margin: 20px auto;
            background-color: #fff;
        }}
        th, td {{
            padding: 12px;
            border: 1px solid #ddd;
            text-align: right;
        }}
        th {{
            background-color: #f4f4f4;
            font-weight: bold;
            text-align: center;
        }}
        th:nth-child(1) {{
            width: 30%;
        }}
        th:nth-child(2) {{
            width: 10%;
        }}
        th:nth-child(3) {{
            width: 10%;
        }}
        th:nth-child(4) {{
            width: 15%;
        }}
        th:nth-child(5) {{
            width: 15%;
        }}
        th:nth-child(6) {{
            width: 10%;
        }}
        th:nth-child(7) {{
            width: 10%;
        }}
        .optimized {{
            background-color: #ddeedd;
        }}
        .copy-icon {{
            cursor: pointer;
            margin-left: 5px;
        }}
        .toggle-button {{
            margin: 20px;
            text-align: center;
        }}
        .thumbnail {{
            position: relative;
            display: inline-block;
        }}
        .thumbnail:hover .thumbnail-image {{
            visibility: visible;
        }}
        .thumbnail-image {{
            visibility: hidden;
            position: absolute;
            z-index: 1;
            width: 200px;
            height: auto;
            top: -10px;
            left: 105%;
            border: 1px solid #ddd;
            background-color: white;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            background-image: linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc),
                              linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc);
            background-size: 20px 20px;
            background-position: 0 0, 10px 10px;
        }}
    </style>
    <script>
        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(function() {{
                console.log('Copied to clipboard successfully!');
            }}, function(err) {{
                console.error('Could not copy text: ', err);
            }});
        }}

        function toggleImages() {{
            var showOptimized = document.getElementById('toggleButton').checked;
            var rows = document.getElementsByClassName('image-row');
            for (var i = 0; i < rows.length; i++) {{
                if (!showOptimized) {{
                    rows[i].style.display = 'table-row';
                }} else {{
                    if (rows[i].classList.contains('optimized')) {{
                        rows[i].style.display = 'table-row';
                    }} else {{
                        rows[i].style.display = 'none';
                    }}
                }}
            }}
        }}
    </script>
</head>
<body onload="toggleImages()">
    <h1>Texture Compactor Scanning Report</h1>
    <div class="total-savings">
        {total_savings}
    </div>
    <div class="toggle-button">
        <label><input type="checkbox" id="toggleButton" onchange="toggleImages()" {checked}>Only Show Images Available for Optimization</label>
    </div>
    <table>
        <thead>
            <tr>
                <th>Image Name</th>
                <th>Original Depth</th>
                <th>Optimized Depth</th>
                <th>Original Resolution</th>
                <th>Optimized Resolution</th>
                <th>Texture Memory (MB)</th>
                <th>Optimized Memory (MB)</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    <div class="total-savings">
        {notes}
    </div>
</body>
</html>
"""

row_template = """
<tr class="image-row {highlight}">
    <td title="{filepath}" style="text-align: left;">
        <div class="thumbnail">
            {name}
            <img src="file://{filepath}" class="thumbnail-image" alt="{name}">
        </div>
        <span class="copy-icon" style="text-align: right;" onclick="copyToClipboard('{filepath}')">⧉</span>
    </td>
    <td>{original_bit_depth}</td>
    <td>{new_bit_depth}</td>
    <td>{original_resolution}</td>
    <td>{new_resolution}</td>
    <td style="width: 150px;">
        <div style="width: 100%; height: 18px; display: flex; justify-content: space-between;">
            <div style="background-color: #eee; height:100%; width:{size_percentage:.2f}%"></div>
            <span>{size_original:.2f}</span>
        </div>
    </td>
    <td>{size_optimized:.2f}</td>
</tr>
"""
