PULSONIX_LIBRARY_ASCII "SamacSys ECAD Model"
//268556/383245/2.49/3/3/MOSFET N-Channel

(asciiHeader
	(fileUnits MM)
)
(library Library_1
	(padStyleDef "c120_h70"
		(holeDiam 0.7)
		(padShape (layerNumRef 1) (padShapeType Ellipse)  (shapeWidth 1.200) (shapeHeight 1.200))
		(padShape (layerNumRef 16) (padShapeType Ellipse)  (shapeWidth 1.200) (shapeHeight 1.200))
	)
	(padStyleDef "s120_h70"
		(holeDiam 0.7)
		(padShape (layerNumRef 1) (padShapeType Rect)  (shapeWidth 1.200) (shapeHeight 1.200))
		(padShape (layerNumRef 16) (padShapeType Rect)  (shapeWidth 1.200) (shapeHeight 1.200))
	)
	(textStyleDef "Normal"
		(font
			(fontType Stroke)
			(fontFace "Helvetica")
			(fontHeight 1.27)
			(strokeWidth 0.127)
		)
	)
	(patternDef "ZVN4206ASTZ" (originalName "ZVN4206ASTZ")
		(multiLayer
			(pad (padNum 1) (padStyleRef s120_h70) (pt 0.000, 0.000) (rotation 90))
			(pad (padNum 2) (padStyleRef c120_h70) (pt 2.540, 0.000) (rotation 90))
			(pad (padNum 3) (padStyleRef c120_h70) (pt 5.080, 0.000) (rotation 90))
		)
		(layerContents (layerNumRef 18)
			(attr "RefDes" "RefDes" (pt 2.540, 0.000) (textStyleRef "Normal") (isVisible True))
		)
		(layerContents (layerNumRef 28)
			(line (pt 0.255 1.14) (pt 4.825 1.14) (width 0.025))
		)
		(layerContents (layerNumRef 28)
			(line (pt 4.825 1.14) (pt 4.825 -1.14) (width 0.025))
		)
		(layerContents (layerNumRef 28)
			(line (pt 4.825 -1.14) (pt 0.255 -1.14) (width 0.025))
		)
		(layerContents (layerNumRef 28)
			(line (pt 0.255 -1.14) (pt 0.255 1.14) (width 0.025))
		)
		(layerContents (layerNumRef Courtyard_Top)
			(line (pt -1.6 2.14) (pt 6.68 2.14) (width 0.1))
		)
		(layerContents (layerNumRef Courtyard_Top)
			(line (pt 6.68 2.14) (pt 6.68 -2.14) (width 0.1))
		)
		(layerContents (layerNumRef Courtyard_Top)
			(line (pt 6.68 -2.14) (pt -1.6 -2.14) (width 0.1))
		)
		(layerContents (layerNumRef Courtyard_Top)
			(line (pt -1.6 -2.14) (pt -1.6 2.14) (width 0.1))
		)
		(layerContents (layerNumRef 18)
			(line (pt -1.06 0) (pt -1.06 0) (width 0.1))
		)
		(layerContents (layerNumRef 18)
			(arc (pt -1.11, 0) (radius 0.05) (startAngle .0) (sweepAngle 180.0) (width 0.1))
		)
		(layerContents (layerNumRef 18)
			(line (pt -1.16 0) (pt -1.16 0) (width 0.1))
		)
		(layerContents (layerNumRef 18)
			(arc (pt -1.11, 0) (radius 0.05) (startAngle 180) (sweepAngle 180.0) (width 0.1))
		)
		(layerContents (layerNumRef 18)
			(line (pt 0.255 -1.14) (pt 4.825 -1.14) (width 0.2))
		)
		(layerContents (layerNumRef 18)
			(line (pt 0.255 1.14) (pt 4.825 1.14) (width 0.2))
		)
	)
	(symbolDef "ZVN4206ASTZ" (originalName "ZVN4206ASTZ")

		(pin (pinNum 1) (pt 0 mils 0 mils) (rotation 0) (pinLength 100 mils) (pinDisplay (dispPinName false)) (pinName (text (pt 0 mils -45 mils) (rotation 0]) (justify "UpperLeft") (textStyleRef "Normal"))
		))
		(pin (pinNum 2) (pt 300 mils 400 mils) (rotation 270) (pinLength 100 mils) (pinDisplay (dispPinName false)) (pinName (text (pt 305 mils 400 mils) (rotation 90]) (justify "UpperLeft") (textStyleRef "Normal"))
		))
		(pin (pinNum 3) (pt 300 mils -200 mils) (rotation 90) (pinLength 100 mils) (pinDisplay (dispPinName false)) (pinName (text (pt 305 mils -200 mils) (rotation 90]) (justify "LowerLeft") (textStyleRef "Normal"))
		))
		(line (pt 300 mils 100 mils) (pt 300 mils -100 mils) (width 6 mils))
		(line (pt 300 mils 200 mils) (pt 300 mils 300 mils) (width 6 mils))
		(line (pt 100 mils 0 mils) (pt 200 mils 0 mils) (width 6 mils))
		(line (pt 200 mils 0 mils) (pt 200 mils 200 mils) (width 6 mils))
		(line (pt 300 mils 100 mils) (pt 230 mils 100 mils) (width 6 mils))
		(line (pt 300 mils 200 mils) (pt 230 mils 200 mils) (width 6 mils))
		(line (pt 230 mils 0 mils) (pt 300 mils 0 mils) (width 6 mils))
		(line (pt 230 mils 220 mils) (pt 230 mils 180 mils) (width 6 mils))
		(line (pt 230 mils -20 mils) (pt 230 mils 20 mils) (width 6 mils))
		(line (pt 230 mils 80 mils) (pt 230 mils 120 mils) (width 6 mils))
		(arc (pt 250 mils 100 mils) (radius 150 mils) (startAngle 0) (sweepAngle 360) (width 10  mils))
		(poly (pt 230 mils 100 mils) (pt 270 mils 120 mils) (pt 270 mils 80 mils) (pt 230 mils 100 mils) (width 10  mils))
		(attr "RefDes" "RefDes" (pt 450 mils 150 mils) (justify Left) (isVisible True) (textStyleRef "Normal"))
		(attr "Type" "Type" (pt 450 mils 50 mils) (justify Left) (isVisible True) (textStyleRef "Normal"))

	)
	(compDef "ZVN4206ASTZ" (originalName "ZVN4206ASTZ") (compHeader (numPins 3) (numParts 1) (refDesPrefix Q)
		)
		(compPin "1" (pinName "D") (partNum 1) (symPinNum 2) (gateEq 0) (pinEq 0) (pinType Bidirectional))
		(compPin "2" (pinName "G") (partNum 1) (symPinNum 1) (gateEq 0) (pinEq 0) (pinType Bidirectional))
		(compPin "3" (pinName "S") (partNum 1) (symPinNum 3) (gateEq 0) (pinEq 0) (pinType Bidirectional))
		(attachedSymbol (partNum 1) (altType Normal) (symbolName "ZVN4206ASTZ"))
		(attachedPattern (patternNum 1) (patternName "ZVN4206ASTZ")
			(numPads 3)
			(padPinMap
				(padNum 1) (compPinRef "1")
				(padNum 2) (compPinRef "2")
				(padNum 3) (compPinRef "3")
			)
		)
		(attr "Manufacturer_Name" "Diodes Inc.")
		(attr "Manufacturer_Part_Number" "ZVN4206ASTZ")
		(attr "Mouser Part Number" "522-ZVN4206ASTZ")
		(attr "Mouser Price/Stock" "https://www.mouser.co.uk/ProductDetail/Diodes-Incorporated/ZVN4206ASTZ?qs=OlC7AqGiEDlGIiNe7stL%252BQ%3D%3D")
		(attr "Arrow Part Number" "ZVN4206ASTZ")
		(attr "Arrow Price/Stock" "https://www.arrow.com/en/products/zvn4206astz/diodes-incorporated?region=nac")
		(attr "Mouser Testing Part Number" "")
		(attr "Mouser Testing Price/Stock" "")
		(attr "Description" "N-Channel 60 V 600mA (Ta) 700mW (Ta) Through Hole E-Line (TO-92 compatible)")
		(attr "<Hyperlink>" "https://www.diodes.com/assets/Datasheets/ZVN4206A.pdf")
		(attr "<Component Height>" "4.01")
		(attr "<STEP Filename>" "ZVN4206ASTZ.stp")
		(attr "<STEP Offsets>" "X=0;Y=0;Z=0")
		(attr "<STEP Rotation>" "X=0;Y=0;Z=0")
	)

)
