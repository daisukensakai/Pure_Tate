R = QQ[a..f];
M = genericMatrix(R,a,2,3);
I = minors(2,M);
print("rank-drop ideal codimension");
print codim I;
