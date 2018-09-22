function searchbar_check() {
	f = document.getElementById('searchbox');
	a = f.elements;

	var l = a.length;
	var s = "";

	for(var i = 0; i < l; i++) {
		if(a[i].id.substring(0,2) === 'u_') {
			if(a[i].checked) s += "," + a[i].value;
		}
	}

	var u  = document.getElementById('user');
	u.value = s.substring(1);
}
