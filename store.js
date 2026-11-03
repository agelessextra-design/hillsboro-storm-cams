/* Rolling image memory. Keeps up to WIN seconds of images per camera, measured back from that camera's newest image. */
var Store=(function(){
  var WIN=3*3600, f={}, onRemove=null;
  function list(id){return f[id]||(f[id]=[])}
  function add(id,ts,src){
    var a=list(id),j=a.length;
    while(j>0&&a[j-1][0]>ts)j--;
    if(j>0&&a[j-1][0]===ts)return null;
    a.splice(j,0,[ts,src]);
    var cut=a[a.length-1][0]-WIN,removed=[];
    while(a.length&&a[0][0]<cut){removed.push(a.shift())}
    if(removed.length&&onRemove)removed.forEach(function(r){onRemove(id,r)});
    return {removed:removed};
  }
  function at(id,t){
    var a=f[id];if(!a||!a.length||a[0][0]>t)return null;
    var lo=0,hi=a.length-1;
    while(lo<hi){var m=(lo+hi+1)>>1;if(a[m][0]<=t)lo=m;else hi=m-1}
    return a[lo];
  }
  function bounds(){
    var mn=Infinity,mx=0;
    for(var k in f){var a=f[k];if(!a.length)continue;if(a[0][0]<mn)mn=a[0][0];if(a[a.length-1][0]>mx)mx=a[a.length-1][0]}
    if(!mx)return {min:0,max:0};
    return {min:Math.max(mn,mx-WIN),max:mx};
  }
  function count(){var n=0;for(var k in f)n+=f[k].length;return n}
  return {add:add,at:at,list:list,bounds:bounds,count:count,WIN:WIN,setOnRemove:function(fn){onRemove=fn}};
})();
if(typeof module!=='undefined')module.exports=Store;
